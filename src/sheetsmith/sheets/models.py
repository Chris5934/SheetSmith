"""Data models for Google Sheets operations."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class CellData(BaseModel):
    """Represents data from a single cell."""

    sheet_name: str
    cell: str  # A1 notation, e.g., "A1", "B2"
    row: int
    col: int
    value: Any = None
    formula: Optional[str] = None
    formatted_value: Optional[str] = None

    @property
    def has_formula(self) -> bool:
        return self.formula is not None and self.formula.startswith("=")


class SheetRange(BaseModel):
    """Represents a range of cells with their data."""

    spreadsheet_id: str
    sheet_name: str
    range_notation: str  # e.g., "Sheet1!A1:C10"
    cells: list[CellData] = Field(default_factory=list)

    @property
    def formulas(self) -> list[CellData]:
        """Return only cells that contain formulas."""
        return [cell for cell in self.cells if cell.has_formula]


class FormulaMatch(BaseModel):
    """Represents a formula that matches a search pattern."""

    spreadsheet_id: str
    sheet_name: str
    cell: str
    row: int
    col: int
    formula: str
    matched_text: str  # The portion that matched the pattern
    context: Optional[str] = None  # Surrounding context if available


class CellUpdate(BaseModel):
    """Represents a single cell update."""

    sheet_name: str
    cell: str  # A1 notation
    new_value: Optional[str] = None
    new_formula: Optional[str] = None

    @property
    def range_notation(self) -> str:
        return f"{self.sheet_name}!{self.cell}"


class BatchUpdate(BaseModel):
    """Represents a batch of cell updates."""

    spreadsheet_id: str
    updates: list[CellUpdate] = Field(default_factory=list)
    description: str = ""

    def add_update(
        self,
        sheet_name: str,
        cell: str,
        new_value: Optional[str] = None,
        new_formula: Optional[str] = None,
    ):
        """Add a cell update to the batch."""
        self.updates.append(
            CellUpdate(
                sheet_name=sheet_name,
                cell=cell,
                new_value=new_value,
                new_formula=new_formula,
            )
        )

    def get_statistics(self) -> dict:
        """Calculate statistics about this batch update."""
        if not self.updates:
            return {
                "total_cells": 0,
                "affected_sheets": [],
                "affected_columns": [],
                "sheet_count": 0,
                "column_count": 0,
            }

        sheets = set()
        columns = set()

        for update in self.updates:
            sheets.add(update.sheet_name)
            # Extract column from cell notation (e.g., "A1" -> "A")
            col = "".join(c for c in update.cell if c.isalpha())
            columns.add(col)

        return {
            "total_cells": len(self.updates),
            "affected_sheets": sorted(list(sheets)),
            "affected_columns": sorted(list(columns)),
            "sheet_count": len(sheets),
            "column_count": len(columns),
        }


class UpdateResult(BaseModel):
    """Result of applying updates."""

    success: bool
    spreadsheet_id: str
    updated_cells: int = 0
    errors: list[str] = Field(default_factory=list)
    details: list[dict] = Field(default_factory=list)


class Patch(BaseModel):
    """Represents a proposed change to formulas."""

    id: str
    spreadsheet_id: str
    description: str
    changes: list[dict] = Field(default_factory=list)  # List of {cell, old, new}
    created_at: str
    status: str = "pending"  # pending, approved, applied, rejected

    def to_diff_string(self) -> str:
        """Generate a human-readable diff."""
        lines = [f"Patch: {self.description}", f"Spreadsheet: {self.spreadsheet_id}", ""]
        for change in self.changes:
            lines.append(f"--- {change['sheet']}!{change['cell']}")
            lines.append(f"-  {change['old']}")
            lines.append(f"+  {change['new']}")
            lines.append("")
        return "\n".join(lines)
