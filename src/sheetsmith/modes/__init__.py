"""Operation modes for SheetSmith - deterministic vs AI-assist."""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class OperationMode(str, Enum):
    """Mode for processing operations."""
    
    DETERMINISTIC = "deterministic"  # Default - no LLM, pure logic
    AI_ASSIST = "ai_assist"  # Optional - LLM helps resolve ambiguity


class OperationRequest(BaseModel):
    """Base request for any operation."""
    
    mode: OperationMode = Field(
        default=OperationMode.DETERMINISTIC,
        description="Processing mode - deterministic or AI-assist"
    )
    operation_type: str = Field(
        description="Type of operation to perform"
    )
    spreadsheet_id: str = Field(
        description="Target spreadsheet ID"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters"
    )


class DeterministicReplaceRequest(BaseModel):
    """Request for deterministic replace operation."""
    
    spreadsheet_id: str
    header_text: str = Field(description="Exact column header name")
    find: str = Field(description="Text to find")
    replace: str = Field(description="Replacement text")
    sheet_names: Optional[list[str]] = Field(
        default=None,
        description="Specific sheets to target (all if None)"
    )
    case_sensitive: bool = Field(default=False)
    is_regex: bool = Field(default=False)


class SetValueRequest(BaseModel):
    """Request to set value by header + row label intersection."""
    
    spreadsheet_id: str
    sheet_name: str = Field(description="Target sheet name")
    header: str = Field(description="Column header text")
    row_label: str = Field(description="Row identifier/label")
    value: Any = Field(description="New value to set")


class AIAssistRequest(BaseModel):
    """Request for AI-assisted operation interpretation."""
    
    spreadsheet_id: str
    request: str = Field(description="Natural language description of operation")
    context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional context for AI interpretation"
    )


class ModeSwitchRequest(BaseModel):
    """Request to switch between modes."""
    
    from_mode: OperationMode
    to_mode: OperationMode
    operation_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Current operation data to carry over"
    )


__all__ = [
    "OperationMode",
    "OperationRequest",
    "DeterministicReplaceRequest",
    "SetValueRequest",
    "AIAssistRequest",
    "ModeSwitchRequest",
]
