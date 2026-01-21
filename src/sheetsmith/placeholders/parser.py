"""Parser for extracting placeholders from formulas."""

import logging
from typing import Optional

from .models import Placeholder, PlaceholderType, ValidationResult
from .syntax import (
    HEADER_PATTERN,
    INTERSECTION_PATTERN,
    CROSS_SHEET_PATTERN,
    VARIABLE_PATTERN,
    ANY_PLACEHOLDER_PATTERN,
    is_valid_placeholder_name,
)

logger = logging.getLogger(__name__)


class PlaceholderParser:
    """Parse and extract placeholders from formulas."""

    def extract_placeholders(self, formula: str) -> list[Placeholder]:
        """
        Extract all placeholders from a formula.

        Args:
            formula: The formula string to parse

        Returns:
            List of Placeholder objects found in the formula
        """
        placeholders = []

        # Find all placeholders in the formula
        for match in ANY_PLACEHOLDER_PATTERN.finditer(formula):
            placeholder_text = match.group(0)
            start_pos = match.start()
            end_pos = match.end()

            # Determine placeholder type and extract details
            placeholder = self._parse_placeholder(placeholder_text, start_pos, end_pos)

            if placeholder:
                placeholders.append(placeholder)
                logger.debug(f"Found placeholder: {placeholder.syntax} (type: {placeholder.type})")

        return placeholders

    def _parse_placeholder(
        self, text: str, start_pos: int, end_pos: int
    ) -> Optional[Placeholder]:
        """
        Parse a single placeholder text and create a Placeholder object.

        Args:
            text: The placeholder text (e.g., "{{base_damage}}")
            start_pos: Start position in formula
            end_pos: End position in formula

        Returns:
            Placeholder object or None if invalid
        """
        # Try to match as cross-sheet reference first
        cross_sheet_match = CROSS_SHEET_PATTERN.match(text)
        if cross_sheet_match:
            # Extract sheet name (could be with quotes or without)
            sheet_name = cross_sheet_match.group(1) or cross_sheet_match.group(2)
            header_name = cross_sheet_match.group(3)

            if not is_valid_placeholder_name(header_name):
                logger.warning(f"Invalid placeholder name: {header_name}")
                return None

            return Placeholder(
                name=header_name.strip(),
                type=PlaceholderType.CROSS_SHEET,
                syntax=text,
                sheet=sheet_name,
                start_pos=start_pos,
                end_pos=end_pos,
            )

        # Try to match as intersection (header:row_label)
        intersection_match = INTERSECTION_PATTERN.match(text)
        if intersection_match:
            header_name = intersection_match.group(1)
            row_label = intersection_match.group(2)

            if not is_valid_placeholder_name(header_name):
                logger.warning(f"Invalid placeholder name: {header_name}")
                return None

            return Placeholder(
                name=header_name.strip(),
                type=PlaceholderType.INTERSECTION,
                syntax=text,
                row_label=row_label.strip(),
                start_pos=start_pos,
                end_pos=end_pos,
            )

        # Try to match as simple header reference
        header_match = HEADER_PATTERN.match(text)
        if header_match:
            header_name = header_match.group(1)

            if not is_valid_placeholder_name(header_name):
                logger.warning(f"Invalid placeholder name: {header_name}")
                return None

            return Placeholder(
                name=header_name.strip(),
                type=PlaceholderType.HEADER,
                syntax=text,
                start_pos=start_pos,
                end_pos=end_pos,
            )

        # Try to match as variable
        variable_match = VARIABLE_PATTERN.match(text)
        if variable_match:
            variable_name = variable_match.group(1)

            return Placeholder(
                name=variable_name.strip(),
                type=PlaceholderType.VARIABLE,
                syntax=text,
                start_pos=start_pos,
                end_pos=end_pos,
            )

        logger.warning(f"Could not parse placeholder: {text}")
        return None

    def validate_syntax(self, formula: str) -> ValidationResult:
        """
        Validate placeholder syntax in a formula.

        Args:
            formula: The formula to validate

        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []

        # Extract placeholders
        placeholders = self.extract_placeholders(formula)

        # Check for malformed brackets
        open_double = formula.count("{{")
        close_double = formula.count("}}")
        if open_double != close_double:
            errors.append(
                f"Mismatched placeholder brackets: {open_double} opening, {close_double} closing"
            )

        # Check for empty placeholders
        if "{{ }}" in formula or "{{  }}" in formula:
            errors.append("Empty placeholders are not allowed")

        # Check for invalid characters in placeholders
        for placeholder in placeholders:
            if not is_valid_placeholder_name(placeholder.name):
                errors.append(
                    f"Invalid placeholder name '{placeholder.name}': "
                    f"must start with a letter and contain only alphanumerics and underscores"
                )

        # Check if formula starts with =
        if formula.strip() and not formula.strip().startswith("="):
            warnings.append("Formula does not start with '=' - this may not be a valid formula")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_placeholder_types(self, formula: str) -> dict[str, PlaceholderType]:
        """
        Get a mapping of placeholder syntax to type.

        Args:
            formula: The formula to analyze

        Returns:
            Dict mapping placeholder syntax to PlaceholderType
        """
        placeholders = self.extract_placeholders(formula)
        return {p.syntax: p.type for p in placeholders}
