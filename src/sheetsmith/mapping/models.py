"""Data models for header-based mapping system."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class MappingStatus(str, Enum):
    """Status of a mapping."""

    VALID = "valid"  # ✅ Header exists and is in expected position
    MOVED = "moved"  # ⚠️ Header exists but in different position
    MISSING = "missing"  # ❌ Header not found
    AMBIGUOUS = "ambiguous"  # ⚠️ Multiple columns with same header


class ColumnMapping(BaseModel):
    """Mapping of a column by its header text."""

    id: Optional[int] = None
    spreadsheet_id: str
    sheet_name: str
    header_text: str
    column_letter: str  # Current position (e.g., "A", "B", "C")
    column_index: int  # 0-based index
    header_row: int = 0  # Row where header was found
    last_validated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utc_now)
    needs_disambiguation: bool = False
    disambiguation_context: Optional[dict[str, Any]] = None


class CellMapping(BaseModel):
    """Mapping of a concept cell by column header × row label intersection."""

    id: Optional[int] = None
    spreadsheet_id: str
    sheet_name: str
    column_header: str
    row_label: str
    cell_address: str  # e.g., "B5"
    row_index: int  # Row where the row_label was found
    column_letter: str  # Current column position
    column_index: int  # 0-based column index
    last_validated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utc_now)
    disambiguation_context: Optional[dict[str, Any]] = None


class ColumnCandidate(BaseModel):
    """A candidate column when multiple columns have the same header."""

    column_letter: str
    column_index: int
    header_row: int
    sample_values: list[str] = Field(default_factory=list)  # Sample values from column
    adjacent_headers: dict[str, Optional[str]] = Field(default_factory=dict)  # left/right headers


class DisambiguationRequest(BaseModel):
    """Request for user to disambiguate between multiple matching columns."""

    request_id: str
    spreadsheet_id: str
    sheet_name: str
    header_text: str
    candidates: list[ColumnCandidate]
    created_at: datetime = Field(default_factory=_utc_now)


class DisambiguationResponse(BaseModel):
    """User's response to a disambiguation request."""

    request_id: str
    selected_column_index: int
    user_label: Optional[str] = None  # Optional user-provided label for this column


class ValidationResult(BaseModel):
    """Result of validating a mapping."""

    is_valid: bool
    status: MappingStatus
    message: str
    old_column_letter: Optional[str] = None  # If column moved
    new_column_letter: Optional[str] = None  # If column moved
    requires_disambiguation: bool = False
    candidates: list[ColumnCandidate] = Field(default_factory=list)


class MappingAuditEntry(BaseModel):
    """Single entry in a mapping audit report."""

    mapping_id: int
    mapping_type: str  # "column" or "cell"
    spreadsheet_id: str
    sheet_name: str
    header_text: Optional[str] = None
    row_label: Optional[str] = None
    current_address: str  # Column letter or cell address
    status: MappingStatus
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    needs_action: bool  # True if user action required


class MappingAuditReport(BaseModel):
    """Report of all mappings for a spreadsheet."""

    spreadsheet_id: str
    spreadsheet_title: Optional[str] = None
    total_mappings: int
    valid_count: int
    moved_count: int
    missing_count: int
    ambiguous_count: int
    entries: list[MappingAuditEntry]
    generated_at: datetime = Field(default_factory=_utc_now)


class DisambiguationRequiredError(Exception):
    """Exception raised when disambiguation is required."""

    def __init__(self, request: DisambiguationRequest):
        self.request = request
        super().__init__(
            f"Multiple columns found with header '{request.header_text}' - "
            f"disambiguation required (request_id: {request.request_id})"
        )


class MappingNotFoundError(Exception):
    """Exception raised when a requested mapping is not found."""

    pass


class HeaderNotFoundError(Exception):
    """Exception raised when a header is not found in the spreadsheet."""

    pass
