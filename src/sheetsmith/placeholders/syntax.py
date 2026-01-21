"""Placeholder syntax definitions and patterns."""

import re
from typing import Pattern

# Placeholder syntax patterns
# {{header_name}} - Column by header name (current row)
HEADER_PATTERN: Pattern = re.compile(r"\{\{([^{}:]+)\}\}")

# {{header_name:row_label}} - Specific cell by header + row intersection
INTERSECTION_PATTERN: Pattern = re.compile(r"\{\{([^{}:]+):([^{}:]+)\}\}")

# 'Sheet'!{{header}} or {Sheet!header} - Cross-sheet reference
CROSS_SHEET_PATTERN: Pattern = re.compile(r"(?:'([^']+)'!|([A-Za-z0-9_]+)!)\{\{([^{}]+)\}\}")

# ${variable} - Stored variable/constant
VARIABLE_PATTERN: Pattern = re.compile(r"\$\{([^{}]+)\}")

# Combined pattern to detect any placeholder
ANY_PLACEHOLDER_PATTERN: Pattern = re.compile(
    r"(?:'[^']+'!|\w+!)?\{\{[^{}:]+(?::[^{}:]+)?\}\}|\$\{[^{}]+\}"
)


def normalize_name(name: str) -> str:
    """
    Normalize a placeholder or header name for matching.

    This handles common variations like:
    - Case differences (Base Damage vs base_damage)
    - Underscores vs spaces (base_damage vs Base Damage)
    - Extra whitespace

    Args:
        name: The name to normalize

    Returns:
        Normalized name (lowercase, spaces removed, trimmed)
    """
    return name.strip().lower().replace(" ", "").replace("_", "")


def fuzzy_match_score(placeholder_name: str, header_text: str) -> float:
    """
    Calculate fuzzy match score between placeholder name and header text.

    Returns:
        Score from 0.0 to 1.0, where 1.0 is exact match
    """
    # Normalize both strings
    norm_placeholder = normalize_name(placeholder_name)
    norm_header = normalize_name(header_text)

    # Exact match after normalization
    if norm_placeholder == norm_header:
        return 1.0

    # Check if one contains the other
    if norm_placeholder in norm_header:
        return 0.9

    if norm_header in norm_placeholder:
        return 0.85

    # Calculate simple similarity based on common characters
    common = set(norm_placeholder) & set(norm_header)
    max_len = max(len(norm_placeholder), len(norm_header))

    if max_len == 0:
        return 0.0

    return len(common) / max_len * 0.7


def is_valid_placeholder_name(name: str) -> bool:
    """
    Check if a placeholder name is valid.

    Valid names:
    - Must not be empty
    - Must not contain special characters except underscore
    - Must not start with a number

    Args:
        name: The placeholder name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or not name.strip():
        return False

    # Remove whitespace for checking
    clean_name = name.strip()

    # Must not start with a number
    if clean_name[0].isdigit():
        return False

    # Can only contain alphanumeric, underscore, and space
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_\s]*$", clean_name))
