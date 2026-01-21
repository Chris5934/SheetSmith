"""Preview generation for operations."""

import re
import uuid
import logging
from typing import Optional
from datetime import datetime, timedelta

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
from ..config import settings

logger = logging.getLogger(__name__)


class PreviewGenerator:
    """Generates previews of operations before applying them."""

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        search_engine: Optional[CellSearchEngine] = None,
    ):
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.search_engine = search_engine or CellSearchEngine(self.sheets_client)
        self.differ = FormulaDiffer()

    def generate_preview(
        self,
        spreadsheet_id: str,
        operation: Operation,
        ttl_minutes: int = 30,
    ) -> PreviewResponse:
        """
        Generate a preview of the operation.
        
        Args:
            spreadsheet_id: The spreadsheet ID
            operation: The operation to preview
            ttl_minutes: Time to live for the preview
            
        Returns:
            PreviewResponse with changes and metadata
        """
        logger.info(f"Generating preview for operation: {operation.operation_type}")
        
        # Generate changes based on operation type
        if operation.operation_type == OperationType.REPLACE_IN_FORMULAS:
            changes = self._preview_replace_in_formulas(spreadsheet_id, operation)
        elif operation.operation_type == OperationType.SET_VALUE_BY_HEADER:
            changes = self._preview_set_value_by_header(spreadsheet_id, operation)
        elif operation.operation_type == OperationType.BULK_FORMULA_UPDATE:
            changes = self._preview_bulk_formula_update(spreadsheet_id, operation)
        else:
            raise ValueError(f"Unsupported operation type: {operation.operation_type}")
        
        # Calculate scope
        scope = self._calculate_scope(changes)
        
        # Generate diff text
        diff_text = self._generate_diff_text(changes)
        
        # Create preview response
        preview_id = str(uuid.uuid4())
        
        return PreviewResponse(
            preview_id=preview_id,
            spreadsheet_id=spreadsheet_id,
            operation_type=operation.operation_type,
            description=operation.description,
            changes=changes,
            scope=scope,
            diff_text=diff_text,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
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
        """Calculate scope information from changes."""
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

    def _generate_diff_text(self, changes: list[ChangeSpec]) -> str:
        """Generate human-readable diff text."""
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
