"""Scope analyzer for operations."""

from typing import Optional
from .safety import OperationScope


class ScopeAnalyzer:
    """Analyzes the scope of operations before execution."""
    
    def __init__(self, sheets_client):
        """
        Initialize scope analyzer.
        
        Args:
            sheets_client: Google Sheets client for analysis
        """
        self.sheets_client = sheets_client
    
    def analyze_from_changes(
        self,
        changes: list,
        operation_type: str = "unknown"
    ) -> OperationScope:
        """
        Analyze scope from a list of change specifications.
        
        Args:
            changes: List of changes (ChangeSpec objects)
            operation_type: Type of operation being performed
            
        Returns:
            OperationScope with detailed metrics
        """
        if not changes:
            return OperationScope(
                total_cells=0,
                total_sheets=0,
                affected_sheets=[],
                affected_columns=[],
                affected_rows=[],
                estimated_duration_ms=0.0,
                risk_level="low"
            )
        
        # Extract unique sheets
        affected_sheets = list(set(
            change.sheet_name for change in changes
        ))
        
        # Extract unique columns from cell addresses
        affected_columns = []
        affected_rows = []
        
        for change in changes:
            # Extract column letter from cell address (e.g., "A1" -> "A")
            cell = change.cell
            col_letters = ''.join(c for c in cell if c.isalpha())
            if col_letters and col_letters not in affected_columns:
                affected_columns.append(col_letters)
            
            # Extract row number from cell address (e.g., "A1" -> 1)
            row_num = ''.join(c for c in cell if c.isdigit())
            if row_num:
                row_int = int(row_num)
                if row_int not in affected_rows:
                    affected_rows.append(row_int)
        
        affected_rows = sorted(affected_rows)
        
        # Estimate duration (rough heuristic: 10ms per cell)
        estimated_duration = len(changes) * 10.0
        
        # Assess risk
        risk = self._assess_risk(len(changes), len(affected_sheets))
        
        return OperationScope(
            total_cells=len(changes),
            total_sheets=len(affected_sheets),
            affected_sheets=affected_sheets,
            affected_columns=affected_columns,
            affected_rows=affected_rows,
            estimated_duration_ms=estimated_duration,
            risk_level=risk
        )
    
    def _assess_risk(self, total_cells: int, total_sheets: int) -> str:
        """
        Assess risk level based on scope metrics.
        
        Args:
            total_cells: Number of cells affected
            total_sheets: Number of sheets affected
            
        Returns:
            Risk level: "low", "medium", or "high"
        """
        if total_cells > 300 or total_sheets > 30:
            return "high"
        elif total_cells > 100 or total_sheets > 10:
            return "medium"
        else:
            return "low"
