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


@dataclass
class OperationScope:
    """Analysis of operation scope (enhanced model per spec)."""
    total_cells: int
    total_sheets: int
    affected_sheets: list[str]
    affected_columns: list[str]
    affected_rows: list[int]
    estimated_duration_ms: float
    risk_level: str  # "low", "medium", "high"


@dataclass
class SafetyCheck:
    """Result of safety validation (enhanced model per spec)."""
    allowed: bool
    warnings: list[str]
    errors: list[str]
    scope: OperationScope
    requires_confirmation: bool
    requires_preview: bool


class SafetyValidator:
    """Validates operations against safety constraints."""

    def __init__(self):
        self.max_cells = settings.max_cells_per_operation
        self.max_sheets = settings.max_sheets_per_operation
        self.max_formula_length = settings.max_formula_length
        self.preview_threshold = settings.require_preview_above_cells

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

    def validate_operation_with_scope(
        self,
        operation_type: str,
        scope: OperationScope,
        dry_run: bool = False
    ) -> SafetyCheck:
        """
        Validate an operation against safety rules (enhanced method per spec).
        
        Args:
            operation_type: Type of operation being validated
            scope: Detailed scope analysis of the operation
            dry_run: If True, operation is for preview only
            
        Returns:
            SafetyCheck with validation results
        """
        errors = []
        warnings = []
        
        # Check cell count limit
        if scope.total_cells > self.max_cells:
            errors.append(
                f"Operation affects {scope.total_cells} cells, "
                f"exceeds limit of {self.max_cells}. Narrow scope."
            )
        
        # Check sheet count limit
        if scope.total_sheets > self.max_sheets:
            errors.append(
                f"Operation affects {scope.total_sheets} sheets, "
                f"exceeds limit of {self.max_sheets}. Narrow scope."
            )
        
        # Warning for large operations
        if scope.total_cells > self.preview_threshold:
            warnings.append(
                f"Large operation ({scope.total_cells} cells). "
                "Preview required before execution."
            )
        
        # Determine risk level if not already set
        risk_level = scope.risk_level or self._assess_risk(scope)
        
        return SafetyCheck(
            allowed=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            scope=scope,
            requires_confirmation=risk_level in ["medium", "high"],
            requires_preview=(
                scope.total_cells > self.preview_threshold or
                risk_level == "high"
            )
        )
    
    def _assess_risk(self, scope: OperationScope) -> str:
        """Assess risk level of operation."""
        if scope.total_cells > self.max_cells * 0.8:
            return "high"
        elif scope.total_cells > self.max_cells * 0.5:
            return "medium"
        else:
            return "low"
    
    def validate_formula_length(self, formula: str) -> tuple[bool, Optional[str]]:
        """Check if formula length is within limits."""
        if len(formula) > self.max_formula_length:
            return False, (
                f"Formula length ({len(formula)}) exceeds limit "
                f"of {self.max_formula_length} characters"
            )
        return True, None

    def requires_preview(self, cells_affected: int) -> bool:
        """Check if operation requires explicit preview/approval."""
        return cells_affected > settings.require_preview_above_cells
