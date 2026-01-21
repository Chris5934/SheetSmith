"""Placeholder mapping system for formula resolution.

This module provides functionality to parse formulas with placeholders
(like {{column_name}}) and resolve them to actual cell references without
generating formula logic.
"""

from .models import (
    Placeholder,
    PlaceholderType,
    ResolvedFormula,
    PlaceholderMapping,
    ValidationResult,
    ResolutionContext,
    MappingPreview,
    MappingSuggestion,
)
from .parser import PlaceholderParser
from .resolver import PlaceholderResolver
from .assistant import PlaceholderAssistant

__all__ = [
    "Placeholder",
    "PlaceholderType",
    "ResolvedFormula",
    "PlaceholderMapping",
    "ValidationResult",
    "ResolutionContext",
    "MappingPreview",
    "MappingSuggestion",
    "PlaceholderParser",
    "PlaceholderResolver",
    "PlaceholderAssistant",
]
