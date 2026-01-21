"""Data models for deterministic operations."""

from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class OperationType(str, Enum):
    """Supported operation types."""

    REPLACE_IN_FORMULAS = "replace_in_formulas"
    SET_VALUE_BY_HEADER = "set_value_by_header"
    COPY_BLOCK = "copy_block"
    BULK_FORMULA_UPDATE = "bulk_formula_update"


class SearchCriteria(BaseModel):
    """Criteria for searching cells."""

    header_text: Optional[str] = None  # Column header name
    row_label: Optional[str] = None  # Row identifier/label
    formula_pattern: Optional[str] = None  # Regex pattern for formula
    value_pattern: Optional[str] = None  # Pattern for value matching
    case_sensitive: bool = False
    is_regex: bool = False
    sheet_names: Optional[list[str]] = None  # Specific sheets to search


class CellMatch(BaseModel):
    """A single cell matching search criteria."""

    spreadsheet_id: str
    sheet_name: str
    cell: str  # A1 notation
    row: int
    col: int
    header: Optional[str] = None  # Column header text
    row_label: Optional[str] = None  # Row label/identifier
    value: Any = None
    formula: Optional[str] = None


class SearchRequest(BaseModel):
    """Request to search for cells."""

    spreadsheet_id: str
    criteria: SearchCriteria
    limit: int = Field(default=1000, ge=1, le=10000)


class SearchResult(BaseModel):
    """Result of a search operation."""

    matches: list[CellMatch]
    total_count: int
    searched_sheets: list[str]
    execution_time_ms: float


class ChangeSpec(BaseModel):
    """Specification for a single change."""

    sheet_name: str
    cell: str  # A1 notation
    old_value: Any = None
    old_formula: Optional[str] = None
    new_value: Any = None
    new_formula: Optional[str] = None
    header: Optional[str] = None  # Column header text
    row_label: Optional[str] = None  # Row label


class Operation(BaseModel):
    """A deterministic operation to perform."""

    operation_type: OperationType
    description: str
    search_criteria: Optional[SearchCriteria] = None
    changes: list[ChangeSpec] = Field(default_factory=list)
    
    # For replace_in_formulas
    find_pattern: Optional[str] = None
    replace_with: Optional[str] = None
    
    # For set_value_by_header
    header_name: Optional[str] = None
    row_labels: Optional[list[str]] = None
    new_values: Optional[dict[str, Any]] = None  # row_label -> value mapping


class PreviewRequest(BaseModel):
    """Request to preview changes."""

    spreadsheet_id: str
    operation: Operation


class ScopeInfo(BaseModel):
    """Summary of operation scope."""

    total_cells: int
    affected_sheets: list[str]
    affected_headers: list[str]
    sheet_count: int
    requires_approval: bool


class PreviewResponse(BaseModel):
    """Response containing change preview."""

    preview_id: str
    spreadsheet_id: str
    operation_type: OperationType
    description: str
    changes: list[ChangeSpec]
    scope: ScopeInfo
    diff_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


class ApplyRequest(BaseModel):
    """Request to apply previewed changes."""

    preview_id: str
    confirmation: bool = False


class ApplyResponse(BaseModel):
    """Response after applying changes."""

    success: bool
    preview_id: str
    spreadsheet_id: str
    cells_updated: int
    errors: list[str] = Field(default_factory=list)
    audit_log_id: Optional[str] = None
    applied_at: datetime = Field(default_factory=datetime.utcnow)
