"""Data models for placeholder mapping system."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PlaceholderType(str, Enum):
    """Type of placeholder."""

    HEADER = "header"  # {{header_name}} - Column by header name (current row)
    INTERSECTION = "intersection"  # {{header_name:row_label}} - Specific cell by header + row
    CROSS_SHEET = "cross_sheet"  # {sheet!header} - Cross-sheet reference
    VARIABLE = "variable"  # ${variable} - Stored variable/constant


class Placeholder(BaseModel):
    """Represents a placeholder in a formula."""

    name: str  # The placeholder name (e.g., "base_damage")
    type: PlaceholderType
    syntax: str  # Original syntax (e.g., "{{base_damage}}")
    sheet: Optional[str] = None  # For cross-sheet references
    row_label: Optional[str] = None  # For intersection type
    start_pos: int = 0  # Position in formula where placeholder starts
    end_pos: int = 0  # Position in formula where placeholder ends


class PlaceholderMapping(BaseModel):
    """Mapping of a placeholder to a cell reference."""

    placeholder: str  # Original placeholder syntax
    resolved_to: str  # Resolved cell reference (e.g., "F2", "$G$15")
    header: str  # Header text that was matched
    column: str  # Column letter
    row: Optional[int] = None  # Row number (if applicable)
    confidence: float = 1.0  # 1.0 = exact match, < 1.0 = fuzzy match
    sheet_name: Optional[str] = None  # Sheet name for cross-sheet references


class ResolvedFormula(BaseModel):
    """Result of resolving placeholders in a formula."""

    original: str  # Original formula with placeholders
    resolved: str  # Resolved formula with cell references
    mappings: list[PlaceholderMapping]  # All placeholder mappings
    warnings: list[str] = Field(default_factory=list)  # Any warnings during resolution


class ValidationResult(BaseModel):
    """Result of validating placeholder syntax."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResolutionContext(BaseModel):
    """Context for resolving placeholders."""

    current_sheet: str  # Current sheet name
    current_row: int  # Current row number (for relative references)
    spreadsheet_id: str  # Spreadsheet ID
    absolute_references: bool = False  # Use $A$1 instead of A1


class MappingPreview(BaseModel):
    """Preview of placeholder mappings before resolution."""

    formula: str  # Original formula
    placeholders: list[Placeholder]  # Detected placeholders
    potential_mappings: dict[str, list[str]]  # placeholder -> possible matches
    requires_disambiguation: list[str] = Field(default_factory=list)  # Ambiguous placeholders


class MappingSuggestion(BaseModel):
    """LLM suggestion for placeholder mapping."""

    placeholder: str
    suggested_header: str
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Why this mapping was suggested
    alternatives: list[str] = Field(default_factory=list)  # Other possible matches
