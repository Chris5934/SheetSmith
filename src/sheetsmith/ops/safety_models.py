"""Safety, preview, and audit models for operations."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class PreviewDiff(BaseModel):
    """Detailed diff for a single cell change."""

    cell_address: str
    sheet_name: str
    header_name: Optional[str] = None
    row_label: Optional[str] = None
    before_value: str
    after_value: str
    before_formula: Optional[str] = None
    after_formula: Optional[str] = None
    change_type: Literal["value", "formula", "both"]


class ScopeSummary(BaseModel):
    """Summary of operation scope and impact."""

    total_cells: int
    total_sheets: int
    sheet_names: list[str]
    headers_affected: list[str]
    row_range_by_sheet: dict[str, tuple[int, int]] = Field(default_factory=dict)
    formula_patterns_matched: list[str] = Field(default_factory=list)
    estimated_duration_seconds: float = 0.0


class SafetyCheck(BaseModel):
    """Result of safety validation checks."""

    passed: bool
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    limit_breaches: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class MappingAuditEntry(BaseModel):
    """Single entry in mapping audit report."""

    mapping_id: Optional[int] = None
    mapping_type: str  # "column" or "cell"
    sheet_name: str
    header_text: Optional[str] = None
    row_label: Optional[str] = None
    cached_position: Optional[str] = None
    current_position: Optional[str] = None
    status: Literal["valid", "moved", "missing", "ambiguous"]
    issue_details: Optional[str] = None


class AuditReport(BaseModel):
    """Report on mapping health for a spreadsheet."""

    timestamp: str
    spreadsheet_id: str
    mappings_checked: int
    valid_mappings: int
    invalid_mappings: list[MappingAuditEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
