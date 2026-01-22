"""Preview generation for operations."""

import re
import uuid
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from ..sheets import GoogleSheetsClient
from ..engine.differ import FormulaDiffer
from .models import (
    PreviewRequest,
    PreviewResponse,
    Operation,
    OperationType,
    ChangeSpec,
    ScopeInfo,
)
from .search import CellSearchEngine
from .safety_models import PreviewDiff, ScopeSummary, SafetyCheck
from .safety_checker import SafetyChecker
from ..config import settings

logger = logging.getLogger(__name__)


class PreviewGenerator:
    """Generates previews of operations before applying them."""

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        search_engine: Optional[CellSearchEngine] = None,
        safety_checker: Optional[SafetyChecker] = None,
    ):
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.search_engine = search_engine or CellSearchEngine(self.sheets_client)
        self.differ = FormulaDiffer()
        self.safety_checker = safety_checker or SafetyChecker(self.sheets_client)

    def generate_preview(
        self,
        spreadsheet_id: str,
        operation: Operation,
        ttl_minutes: int = 30,
        dry_run: bool = False,
    ) -> PreviewResponse:
        """
        Generate a preview of the operation.
        
        Args:
            spreadsheet_id: The spreadsheet ID
            operation: The operation to preview
            ttl_minutes: Time to live for the preview
            dry_run: If True, only generate preview without storing for apply
            
        Returns:
            PreviewResponse with changes and metadata
        """
        logger.info(
            f"Generating preview for operation: {operation.operation_type} "
            f"(dry_run={dry_run})"
        )
        
        # Generate changes based on operation type
        if operation.operation_type == OperationType.REPLACE_IN_FORMULAS:
            changes = self._preview_replace_in_formulas(spreadsheet_id, operation)
        elif operation.operation_type == OperationType.SET_VALUE_BY_HEADER:
            changes = self._preview_set_value_by_header(spreadsheet_id, operation)
        elif operation.operation_type == OperationType.BULK_FORMULA_UPDATE:
            changes = self._preview_bulk_formula_update(spreadsheet_id, operation)
        else:
            raise ValueError(f"Unsupported operation type: {operation.operation_type}")
        
        # Calculate enhanced scope summary
        scope_summary = self._calculate_enhanced_scope(changes, operation)
        
        # Run safety checks
        safety_check = self.safety_checker.check_operation_safety(operation, scope_summary)
        
        if not safety_check.passed:
            logger.warning(
                f"Safety check failed for preview: {safety_check.errors}"
            )
            # Include safety check info in preview but allow preview generation
            # The actual apply will enforce these limits
        
        # Calculate legacy scope for backwards compatibility
        scope = self._calculate_scope(changes)
        
        # Generate enhanced diff text with formula diffs
        diff_text = self._generate_enhanced_diff_text(changes)
        
        # Create preview response
        preview_id = str(uuid.uuid4())
        
        # Use configured TTL seconds, converting to minutes
        ttl_seconds = getattr(settings, 'preview_ttl_seconds', 300)
        
        return PreviewResponse(
            preview_id=preview_id,
            spreadsheet_id=spreadsheet_id,
            operation_type=operation.operation_type,
            description=operation.description,
            changes=changes,
            scope=scope,
            diff_text=diff_text,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )

    def _preview_replace_in_formulas(
        self, spreadsheet_id: str, operation: Operation
    ) -> list[ChangeSpec]:
        """Preview replace in formulas operation."""
        if not operation.find_pattern or operation.replace_with is None:
            raise ValueError("find_pattern and replace_with are required")
        
        # Search for formulas containing the pattern
        from .models import SearchCriteria
        
        criteria = SearchCriteria(
            formula_pattern=operation.find_pattern,
            case_sensitive=False,
            is_regex=operation.search_criteria.is_regex if operation.search_criteria else False,
            sheet_names=operation.search_criteria.sheet_names if operation.search_criteria else None,
        )
        
        search_result = self.search_engine.search(spreadsheet_id, criteria)
        
        changes = []
        for match in search_result.matches:
            if not match.formula:
                continue
            
            # Perform replacement
            if operation.search_criteria and operation.search_criteria.is_regex:
                try:
                    new_formula = re.sub(
                        operation.find_pattern,
                        operation.replace_with,
                        match.formula,
                    )
                except re.error as e:
                    logger.warning(f"Regex error: {e}")
                    continue
            else:
                new_formula = match.formula.replace(
                    operation.find_pattern, operation.replace_with
                )
            
            # Only include if actually changed
            if new_formula != match.formula:
                changes.append(
                    ChangeSpec(
                        sheet_name=match.sheet_name,
                        cell=match.cell,
                        old_formula=match.formula,
                        old_value=match.value,
                        new_formula=new_formula,
                        header=match.header,
                        row_label=match.row_label,
                    )
                )
        
        return changes

    def _preview_set_value_by_header(
        self, spreadsheet_id: str, operation: Operation
    ) -> list[ChangeSpec]:
        """Preview set value by header operation."""
        if not operation.header_name:
            raise ValueError("header_name is required")
        
        if not operation.row_labels:
            raise ValueError("row_labels is required")
        
        if not operation.new_values:
            raise ValueError("new_values is required")
        
        # Search for cells by header
        from .models import SearchCriteria
        
        criteria = SearchCriteria(
            header_text=operation.header_name,
            case_sensitive=False,
            sheet_names=operation.search_criteria.sheet_names if operation.search_criteria else None,
        )
        
        search_result = self.search_engine.search(spreadsheet_id, criteria)
        
        changes = []
        for match in search_result.matches:
            # Check if this row is in our target row labels
            if match.row_label not in operation.row_labels:
                continue
            
            # Get new value for this row
            new_value = operation.new_values.get(match.row_label)
            if new_value is None:
                continue
            
            # Only include if actually changed
            if str(new_value) != str(match.value):
                changes.append(
                    ChangeSpec(
                        sheet_name=match.sheet_name,
                        cell=match.cell,
                        old_value=match.value,
                        old_formula=match.formula,
                        new_value=new_value,
                        header=match.header,
                        row_label=match.row_label,
                    )
                )
        
        return changes

    def _preview_bulk_formula_update(
        self, spreadsheet_id: str, operation: Operation
    ) -> list[ChangeSpec]:
        """Preview bulk formula update operation."""
        if not operation.search_criteria:
            raise ValueError("search_criteria is required")
        
        if not operation.find_pattern or operation.replace_with is None:
            raise ValueError("find_pattern and replace_with are required")
        
        # Similar to replace_in_formulas but with more flexible criteria
        search_result = self.search_engine.search(spreadsheet_id, operation.search_criteria)
        
        changes = []
        for match in search_result.matches:
            if not match.formula:
                continue
            
            # Perform replacement
            if operation.search_criteria.is_regex:
                try:
                    new_formula = re.sub(
                        operation.find_pattern,
                        operation.replace_with,
                        match.formula,
                    )
                except re.error as e:
                    logger.warning(f"Regex error: {e}")
                    continue
            else:
                new_formula = match.formula.replace(
                    operation.find_pattern, operation.replace_with
                )
            
            # Only include if actually changed
            if new_formula != match.formula:
                changes.append(
                    ChangeSpec(
                        sheet_name=match.sheet_name,
                        cell=match.cell,
                        old_formula=match.formula,
                        old_value=match.value,
                        new_formula=new_formula,
                        header=match.header,
                        row_label=match.row_label,
                    )
                )
        
        return changes

    def _calculate_scope(self, changes: list[ChangeSpec]) -> ScopeInfo:
        """Calculate scope information from changes (legacy format)."""
        affected_sheets = list(set(c.sheet_name for c in changes))
        affected_headers = list(set(c.header for c in changes if c.header))
        
        requires_approval = len(changes) > settings.require_preview_above_cells
        
        return ScopeInfo(
            total_cells=len(changes),
            affected_sheets=affected_sheets,
            affected_headers=affected_headers,
            sheet_count=len(affected_sheets),
            requires_approval=requires_approval,
        )

    def _calculate_enhanced_scope(
        self, changes: list[ChangeSpec], operation: Operation
    ) -> ScopeSummary:
        """Calculate enhanced scope summary with detailed information."""
        affected_sheets = list(set(c.sheet_name for c in changes))
        affected_headers = list(set(c.header for c in changes if c.header))
        
        # Calculate row ranges by sheet
        row_ranges = {}
        for change in changes:
            sheet = change.sheet_name
            row = change.cell
            # Extract row number from A1 notation (e.g., "B2" -> 2)
            try:
                row_num = int(''.join(filter(str.isdigit, row)))
                if sheet not in row_ranges:
                    row_ranges[sheet] = [row_num, row_num]
                else:
                    row_ranges[sheet][0] = min(row_ranges[sheet][0], row_num)
                    row_ranges[sheet][1] = max(row_ranges[sheet][1], row_num)
            except (ValueError, IndexError):
                pass
        
        # Convert to tuple format
        row_range_by_sheet = {
            sheet: tuple(range_list) for sheet, range_list in row_ranges.items()
        }
        
        # Collect formula patterns matched
        formula_patterns = []
        if operation.find_pattern:
            formula_patterns.append(operation.find_pattern)
        
        # Estimate duration (rough estimate: 10ms per cell)
        estimated_duration = len(changes) * 0.01
        
        return ScopeSummary(
            total_cells=len(changes),
            total_sheets=len(affected_sheets),
            sheet_names=affected_sheets,
            headers_affected=affected_headers,
            row_range_by_sheet=row_range_by_sheet,
            formula_patterns_matched=formula_patterns,
            estimated_duration_seconds=estimated_duration,
        )

    def _generate_diff_text(self, changes: list[ChangeSpec]) -> str:
        """Generate human-readable diff text (legacy format)."""
        lines = []
        
        for change in changes:
            lines.append(f"--- {change.sheet_name}!{change.cell}")
            
            if change.old_formula:
                lines.append(f"-  {change.old_formula}")
            elif change.old_value is not None:
                lines.append(f"-  {change.old_value}")
            
            if change.new_formula:
                lines.append(f"+  {change.new_formula}")
            elif change.new_value is not None:
                lines.append(f"+  {change.new_value}")
            
            lines.append("")
        
        return "\n".join(lines)

    def _generate_enhanced_diff_text(self, changes: list[ChangeSpec]) -> str:
        """Generate enhanced diff text with formula highlighting."""
        lines = []
        max_display = getattr(settings, 'max_preview_diffs_displayed', 100)
        
        for idx, change in enumerate(changes[:max_display]):
            # Header with location info
            header_info = f" (Header: {change.header})" if change.header else ""
            row_info = f" (Row: {change.row_label})" if change.row_label else ""
            lines.append(f"--- {change.sheet_name}!{change.cell}{header_info}{row_info}")
            
            # Show before
            if change.old_formula:
                lines.append(f"-  FORMULA: {change.old_formula}")
                if change.old_value is not None:
                    lines.append(f"-  VALUE:   {change.old_value}")
            elif change.old_value is not None:
                lines.append(f"-  {change.old_value}")
            
            # Show after
            if change.new_formula:
                lines.append(f"+  FORMULA: {change.new_formula}")
                # Use differ to highlight changes if both formulas exist
                if change.old_formula:
                    diff = self.differ.diff_formula(
                        change.old_formula, change.new_formula, change.cell, change.sheet_name
                    )
                    if diff.changes:
                        # Show changes summary
                        changes_text = ", ".join([
                            f"{c['type']}: '{c['old']}' -> '{c['new']}'" 
                            for c in diff.changes[:3]  # Show first 3 changes
                        ])
                        lines.append(f"   CHANGES: {changes_text}")
            elif change.new_value is not None:
                lines.append(f"+  {change.new_value}")
            
            lines.append("")
        
        # Add summary if truncated
        if len(changes) > max_display:
            remaining = len(changes) - max_display
            lines.append(f"... and {remaining} more changes (showing first {max_display})")
        
        return "\n".join(lines)

    def generate_preview_diffs(self, changes: list[ChangeSpec]) -> list[PreviewDiff]:
        """Generate detailed PreviewDiff objects for UI consumption."""
        diffs = []
        
        for change in changes:
            # Determine change type
            if change.old_formula and change.new_formula:
                change_type = "both" if change.old_value != change.new_value else "formula"
            elif change.new_formula or change.old_formula:
                change_type = "formula"
            else:
                change_type = "value"
            
            diff = PreviewDiff(
                cell_address=change.cell,
                sheet_name=change.sheet_name,
                header_name=change.header,
                row_label=change.row_label,
                before_value=str(change.old_value) if change.old_value is not None else "",
                after_value=str(change.new_value) if change.new_value is not None else "",
                before_formula=change.old_formula,
                after_formula=change.new_formula,
                change_type=change_type,
            )
            diffs.append(diff)
        
        return diffs
    
    def format_preview_for_display(
        self,
        preview,
        max_changes: int = 20
    ) -> str:
        """
        Format preview as human-readable diff (spec-compliant formatting).
        
        Args:
            preview: PreviewResponse object to format
            max_changes: Maximum number of changes to display
            
        Returns:
            Formatted preview text with scope, warnings, and changes
        """
        from ..engine.safety import OperationScope, SafetyCheck
        
        lines = [
            f"# Preview: {preview.operation_type.value}",
            f"# Preview ID: {preview.preview_id}",
            "",
            "## Scope Analysis",
            f"- Total cells: {preview.scope.total_cells}",
            f"- Affected sheets: {', '.join(preview.scope.affected_sheets)}",
            f"- Affected headers: {', '.join(preview.scope.affected_headers)}",
            f"- Sheet count: {preview.scope.sheet_count}",
            "",
        ]
        
        # Add approval requirement if needed
        if preview.scope.requires_approval:
            lines.append("⚠️  **This operation requires explicit approval**")
            lines.append("")
        
        # Add changes preview
        lines.append("## Changes")
        display_count = min(len(preview.changes), max_changes)
        
        for change in preview.changes[:display_count]:
            lines.append(f"\n### {change.sheet_name}!{change.cell}")
            if change.header:
                lines.append(f"Header: {change.header}")
            if change.row_label:
                lines.append(f"Row: {change.row_label}")
            
            lines.append("```diff")
            if change.old_formula:
                lines.append(f"- FORMULA: {change.old_formula}")
            elif change.old_value is not None:
                lines.append(f"- VALUE: {change.old_value}")
            
            if change.new_formula:
                lines.append(f"+ FORMULA: {change.new_formula}")
            elif change.new_value is not None:
                lines.append(f"+ VALUE: {change.new_value}")
            lines.append("```")
        
        if len(preview.changes) > max_changes:
            remaining = len(preview.changes) - max_changes
            lines.append(f"\n... and {remaining} more changes (showing first {max_changes})")
        
        return "\n".join(lines)
