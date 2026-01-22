"""Data models for the memory/persistence layer."""

from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Rule(BaseModel):
    """A project-specific rule or convention."""

    id: str
    name: str
    description: str
    rule_type: str  # "formula_style", "naming", "structure", "custom"
    content: str  # The actual rule text or pattern
    examples: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    tags: list[str] = Field(default_factory=list)


class LogicBlock(BaseModel):
    """A known reusable logic block (kit, teammate, rotation)."""

    id: str
    name: str
    block_type: str  # "kit", "teammate", "rotation", "custom"
    description: str
    formula_pattern: str  # The formula pattern for this logic
    variables: dict[str, str] = Field(default_factory=dict)  # Variable name -> description
    version: str = "1.0"
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    tags: list[str] = Field(default_factory=list)


class AuditLog(BaseModel):
    """An audit log entry for tracking changes."""

    id: str
    timestamp: datetime = Field(default_factory=_utc_now)
    action: str  # "search", "update", "batch_update", "rule_change"
    spreadsheet_id: Optional[str] = None
    description: str
    details: dict[str, Any] = Field(default_factory=dict)
    user_approved: bool = False
    changes_applied: int = 0


class FixSummary(BaseModel):
    """Summary of a previous fix for reference."""

    id: str
    title: str
    description: str
    spreadsheet_id: str
    timestamp: datetime = Field(default_factory=_utc_now)
    pattern_searched: Optional[str] = None
    cells_modified: int = 0
    before_example: Optional[str] = None
    after_example: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
