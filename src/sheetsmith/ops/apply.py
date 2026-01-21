"""Apply logic for executing previewed operations."""

import uuid
import logging
from typing import Optional
from datetime import datetime

from ..sheets import GoogleSheetsClient, BatchUpdate, CellUpdate
from ..engine.safety import SafetyValidator
from .models import ApplyRequest, ApplyResponse, PreviewResponse, ChangeSpec
from ..memory import MemoryStore, AuditLog

logger = logging.getLogger(__name__)


class ApplyEngine:
    """Executes previewed operations and applies changes to spreadsheets."""

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        memory_store: Optional[MemoryStore] = None,
    ):
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.memory_store = memory_store
        self.safety_validator = SafetyValidator()

    async def apply_changes(
        self, preview: PreviewResponse, confirmation: bool = False
    ) -> ApplyResponse:
        """
        Apply the changes from a preview.
        
        Args:
            preview: The preview containing changes to apply
            confirmation: User confirmation (required for operations requiring approval)
            
        Returns:
            ApplyResponse with results
        """
        logger.info(f"Applying changes from preview {preview.preview_id}")
        
        # Validate that preview hasn't expired
        if datetime.utcnow() > preview.expires_at:
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
        
        # Validate safety constraints
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
                timestamp=datetime.utcnow(),
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
