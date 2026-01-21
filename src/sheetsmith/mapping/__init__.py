"""Header-based mapping module for stable column and cell references."""

from .models import (
    ColumnMapping,
    CellMapping,
    DisambiguationRequest,
    DisambiguationResponse,
    ColumnCandidate,
    MappingStatus,
    ValidationResult,
    MappingAuditReport,
    MappingAuditEntry,
    DisambiguationRequiredError,
    MappingNotFoundError,
    HeaderNotFoundError,
)
from .manager import MappingManager
from .storage import MappingStorage
from .validator import MappingValidator
from .disambiguator import DisambiguationHandler

__all__ = [
    "ColumnMapping",
    "CellMapping",
    "DisambiguationRequest",
    "DisambiguationResponse",
    "ColumnCandidate",
    "MappingStatus",
    "ValidationResult",
    "MappingAuditReport",
    "MappingAuditEntry",
    "DisambiguationRequiredError",
    "MappingNotFoundError",
    "HeaderNotFoundError",
    "MappingManager",
    "MappingStorage",
    "MappingValidator",
    "DisambiguationHandler",
]
