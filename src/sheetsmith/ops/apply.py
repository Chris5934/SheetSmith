"""Apply logic for executing previewed operations."""

import uuid
import logging
from typing import Optional
from datetime import datetime, timezone

from ..sheets import GoogleSheetsClient, BatchUpdate, CellUpdate
from ..engine.safety import SafetyValidator
from .models import ApplyRequest, ApplyResponse, PreviewResponse, ChangeSpec
from .safety_checker import SafetyChecker
from .safety_models import ScopeSummary
from ..memory import MemoryStore, AuditLog
from ..config import settings

logger = logging.getLogger(__name__)


class ApplyEngine:
    """Executes previewed operations and applies changes to spreadsheets."""

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        memory_store: Optional[MemoryStore] = None,
        safety_checker: Optional[SafetyChecker] = None,
    ):
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.memory_store = memory_store
        self.safety_validator = SafetyValidator()
        self.safety_checker = safety_checker or SafetyChecker(self.sheets_client)

    async def apply_changes(
        self, preview: PreviewResponse, confirmation: bool = False, dry_run: bool = False
    ) -> ApplyResponse:
        """
        Apply the changes from a preview.
        
        Args:
            preview: The preview containing changes to apply
            confirmation: User confirmation (required for operations requiring approval)
            dry_run: If True, perform validation but don't actually write to spreadsheet
            
        Returns:
            ApplyResponse with results
        """
        logger.info(
            f"Applying changes from preview {preview.preview_id} (dry_run={dry_run})"
        )
        
        # Validate that preview hasn't expired
        if datetime.now(timezone.utc) > preview.expires_at:
            return ApplyResponse(
                success=False,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=0,
                errors=["Preview has expired. Please generate a new preview."],
            )
        
        # Check if confirmation is required
        if preview.scope.requires_approval and not confirmation:
            return ApplyResponse(
                success=False,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=0,
                errors=[
                    f"This operation affects {preview.scope.total_cells} cells "
                    "and requires explicit confirmation."
                ],
            )
        
        # Re-run safety checks before apply (double-check)
        scope_summary = self._preview_to_scope_summary(preview)
        safety_check = self.safety_checker.check_operation_safety(
            Operation(
                operation_type=preview.operation_type,
                description=preview.description,
            ),
            scope_summary
        )
        
        if not safety_check.passed:
            return ApplyResponse(
                success=False,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=0,
                errors=safety_check.errors,
            )
        
        # Also validate with legacy safety constraints for backwards compatibility
        is_safe, violations = self.safety_validator.validate_operation(
            cells_affected=preview.scope.total_cells,
            sheets_affected=preview.scope.sheet_count,
        )
        
        if not is_safe:
            error_messages = [v.message for v in violations]
            return ApplyResponse(
                success=False,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=0,
                errors=error_messages,
            )
        
        # Dry-run mode: skip actual application
        if dry_run:
            logger.info("Dry-run mode: skipping actual application to spreadsheet")
            
            # Log dry-run to audit trail if memory store is available
            audit_log_id = None
            if self.memory_store:
                audit_log_id = await self._log_dry_run_to_audit_trail(preview)
            
            return ApplyResponse(
                success=True,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=len(preview.changes),
                errors=[],
                audit_log_id=audit_log_id,
            )
        
        # Apply changes
        try:
            result = await self._execute_changes(preview)
            
            # Log to audit trail if memory store is available
            audit_log_id = None
            if self.memory_store:
                audit_log_id = await self._log_to_audit_trail(preview, result)
            
            return ApplyResponse(
                success=result.success,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=result.updated_cells,
                errors=result.errors,
                audit_log_id=audit_log_id,
            )
        
        except Exception as e:
            logger.error(f"Error applying changes: {e}", exc_info=True)
            return ApplyResponse(
                success=False,
                preview_id=preview.preview_id,
                spreadsheet_id=preview.spreadsheet_id,
                cells_updated=0,
                errors=[str(e)],
            )

    async def _execute_changes(self, preview: PreviewResponse):
        """Execute the actual changes to the spreadsheet."""
        batch = BatchUpdate(
            spreadsheet_id=preview.spreadsheet_id,
            updates=[],
            description=preview.description,
        )
        
        # Convert change specs to cell updates
        for change in preview.changes:
            update = CellUpdate(
                sheet_name=change.sheet_name,
                cell=change.cell,
                new_value=str(change.new_value) if change.new_value is not None else None,
                new_formula=change.new_formula,
            )
            batch.updates.append(update)
        
        # Apply batch update
        result = self.sheets_client.batch_update(batch)
        
        logger.info(
            f"Applied {result.updated_cells} cell updates to "
            f"{preview.spreadsheet_id}"
        )
        
        return result

    async def _log_to_audit_trail(
        self, preview: PreviewResponse, result
    ) -> Optional[str]:
        """Log the operation to the audit trail."""
        if not self.memory_store:
            return None
        
        try:
            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=f"ops_{preview.operation_type.value}",
                spreadsheet_id=preview.spreadsheet_id,
                description=preview.description,
                details={
                    "preview_id": preview.preview_id,
                    "operation_type": preview.operation_type.value,
                    "scope": {
                        "total_cells": preview.scope.total_cells,
                        "affected_sheets": preview.scope.affected_sheets,
                        "affected_headers": preview.scope.affected_headers,
                    },
                    "success": result.success,
                },
                user_approved=True,
                changes_applied=result.updated_cells,
            )
            
            await self.memory_store.store_audit_log(audit_log)
            logger.info(f"Logged operation to audit trail: {audit_log.id}")
            return audit_log.id
        
        except Exception as e:
            logger.error(f"Failed to log to audit trail: {e}")
            return None

    async def _log_dry_run_to_audit_trail(
        self, preview: PreviewResponse
    ) -> Optional[str]:
        """Log a dry-run operation to the audit trail."""
        if not self.memory_store:
            return None
        
        try:
            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=f"ops_{preview.operation_type.value}_dry_run",
                spreadsheet_id=preview.spreadsheet_id,
                description=f"[DRY RUN] {preview.description}",
                details={
                    "preview_id": preview.preview_id,
                    "operation_type": preview.operation_type.value,
                    "dry_run": True,
                    "scope": {
                        "total_cells": preview.scope.total_cells,
                        "affected_sheets": preview.scope.affected_sheets,
                        "affected_headers": preview.scope.affected_headers,
                    },
                },
                user_approved=True,
                changes_applied=0,  # No actual changes in dry-run
            )
            
            await self.memory_store.store_audit_log(audit_log)
            logger.info(f"Logged dry-run operation to audit trail: {audit_log.id}")
            return audit_log.id
        
        except Exception as e:
            logger.error(f"Failed to log dry-run to audit trail: {e}")
            return None

    def _preview_to_scope_summary(self, preview: PreviewResponse) -> ScopeSummary:
        """Convert preview to scope summary for safety checks."""
        # Calculate row ranges from changes
        row_ranges = {}
        for change in preview.changes:
            sheet = change.sheet_name
            cell = change.cell
            try:
                row_num = int(''.join(filter(str.isdigit, cell)))
                if sheet not in row_ranges:
                    row_ranges[sheet] = [row_num, row_num]
                else:
                    row_ranges[sheet][0] = min(row_ranges[sheet][0], row_num)
                    row_ranges[sheet][1] = max(row_ranges[sheet][1], row_num)
            except (ValueError, IndexError):
                pass
        
        row_range_by_sheet = {
            sheet: tuple(range_list) for sheet, range_list in row_ranges.items()
        }
        
        return ScopeSummary(
            total_cells=preview.scope.total_cells,
            total_sheets=preview.scope.sheet_count,
            sheet_names=preview.scope.affected_sheets,
            headers_affected=preview.scope.affected_headers,
            row_range_by_sheet=row_range_by_sheet,
            formula_patterns_matched=[],
            estimated_duration_seconds=0.0,
        )
