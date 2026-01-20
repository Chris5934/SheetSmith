"""Safety validation for spreadsheet operations."""

from typing import Optional
from dataclasses import dataclass
from ..config import settings


@dataclass
class SafetyViolation:
    """Represents a safety constraint violation."""

    constraint: str
    current_value: int
    max_value: int
    message: str


class SafetyValidator:
    """Validates operations against safety constraints."""

    def validate_operation(
        self,
        cells_affected: int,
        sheets_affected: int,
        max_formula_length: Optional[int] = None,
    ) -> tuple[bool, list[SafetyViolation]]:
        """
        Validate an operation against safety constraints.

        Returns:
            (is_safe, violations) - True if safe, list of violations if not
        """
        violations = []

        # Check cells limit
        if cells_affected > settings.max_cells_per_operation:
            violations.append(
                SafetyViolation(
                    constraint="max_cells_per_operation",
                    current_value=cells_affected,
                    max_value=settings.max_cells_per_operation,
                    message=f"Operation would affect {cells_affected} cells, exceeding limit of {settings.max_cells_per_operation}",
                )
            )

        # Check sheets limit
        if sheets_affected > settings.max_sheets_per_operation:
            violations.append(
                SafetyViolation(
                    constraint="max_sheets_per_operation",
                    current_value=sheets_affected,
                    max_value=settings.max_sheets_per_operation,
                    message=f"Operation would affect {sheets_affected} sheets, exceeding limit of {settings.max_sheets_per_operation}",
                )
            )

        # Check formula length if provided
        if max_formula_length and max_formula_length > settings.max_formula_length:
            violations.append(
                SafetyViolation(
                    constraint="max_formula_length",
                    current_value=max_formula_length,
                    max_value=settings.max_formula_length,
                    message=f"Formula length {max_formula_length} exceeds limit of {settings.max_formula_length}",
                )
            )

        return len(violations) == 0, violations

    def requires_preview(self, cells_affected: int) -> bool:
        """Check if operation requires explicit preview/approval."""
        return cells_affected > settings.require_preview_above_cells
