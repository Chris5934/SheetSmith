"""Safety checker for validating operations before execution."""

import logging
from typing import Optional
from datetime import datetime, timezone

from ..config import settings
from ..sheets import GoogleSheetsClient
from .models import Operation
from .safety_models import ScopeSummary, SafetyCheck, AuditReport, MappingAuditEntry

logger = logging.getLogger(__name__)


class SafetyChecker:
    """Validates operations against safety constraints and detects ambiguities."""

    def __init__(self, sheets_client: Optional[GoogleSheetsClient] = None):
        """
        Initialize safety checker.

        Args:
            sheets_client: Google Sheets client for validation
        """
        self.sheets_client = sheets_client or GoogleSheetsClient()

    def check_operation_safety(
        self, operation: Operation, scope_summary: ScopeSummary
    ) -> SafetyCheck:
        """
        Run comprehensive safety checks before allowing operation.

        Args:
            operation: The operation to validate
            scope_summary: Scope summary of the operation

        Returns:
            SafetyCheck with validation results
        """
        warnings = []
        errors = []
        limit_breaches = []
        ambiguities = []

        # Check hard limits
        try:
            self.enforce_hard_limits(scope_summary)
        except ValueError as e:
            limit_breaches.append(str(e))
            errors.append(str(e))

        # Check for ambiguities if search criteria provided
        if operation.search_criteria and operation.search_criteria.header_text:
            amb = self.detect_header_ambiguities(
                scope_summary.sheet_names, [operation.search_criteria.header_text]
            )
            ambiguities.extend(amb)
            if amb:
                errors.extend(amb)

        # Check if headers are affected
        if operation.header_name:
            amb = self.detect_header_ambiguities(
                scope_summary.sheet_names, [operation.header_name]
            )
            ambiguities.extend(amb)
            if amb:
                errors.extend(amb)

        # Add warnings for large operations
        if scope_summary.total_cells > settings.require_preview_above_cells:
            warnings.append(
                f"This operation affects {scope_summary.total_cells} cells, "
                f"which exceeds the recommended threshold of {settings.require_preview_above_cells}. "
                "Please review carefully before applying."
            )

        # Check for formula length
        if operation.find_pattern and len(operation.find_pattern) > 1000:
            warnings.append(
                f"Find pattern is very long ({len(operation.find_pattern)} characters). "
                "This may cause performance issues."
            )

        # Determine if check passed
        passed = len(errors) == 0 and len(limit_breaches) == 0

        return SafetyCheck(
            passed=passed,
            warnings=warnings,
            errors=errors,
            limit_breaches=limit_breaches,
            ambiguities=ambiguities,
        )

    def enforce_hard_limits(self, scope: ScopeSummary) -> None:
        """
        Enforce hard safety limits and raise exception if breached.

        Args:
            scope: Scope summary to validate

        Raises:
            ValueError: If any hard limit is breached
        """
        violations = []

        # Check cells limit
        if scope.total_cells > settings.max_cells_per_operation:
            violations.append(
                f"Operation would affect {scope.total_cells} cells, "
                f"exceeding limit of {settings.max_cells_per_operation}. "
                f"Please narrow scope by filtering sheets, headers, or row ranges."
            )

        # Check sheets limit
        if scope.total_sheets > settings.max_sheets_per_operation:
            violations.append(
                f"Operation would affect {scope.total_sheets} sheets, "
                f"exceeding limit of {settings.max_sheets_per_operation}. "
                f"Please target specific sheets or split into smaller operations."
            )

        # Check formula patterns
        for pattern in scope.formula_patterns_matched:
            if len(pattern) > settings.max_formula_length:
                violations.append(
                    f"Formula pattern length {len(pattern)} exceeds "
                    f"limit of {settings.max_formula_length} characters."
                )

        if violations:
            error_msg = "\n".join([f"  • {v}" for v in violations])
            raise ValueError(f"Hard safety limit(s) breached:\n{error_msg}")

        logger.info("All hard safety limits passed")

    def detect_header_ambiguities(
        self, sheet_names: list[str], headers: list[str]
    ) -> list[str]:
        """
        Detect duplicate headers and other ambiguities.

        This is a placeholder implementation that would need access to
        actual spreadsheet data to detect real ambiguities.

        Args:
            sheet_names: List of sheet names to check
            headers: List of header names to validate

        Returns:
            List of ambiguity warnings
        """
        ambiguities = []

        # This is a simplified check - in production would need to
        # actually read the spreadsheet and check for duplicates
        logger.info(
            f"Checking for ambiguities in {len(sheet_names)} sheets "
            f"for {len(headers)} headers"
        )

        # Placeholder: would implement actual duplicate detection here
        # by reading the spreadsheet and checking header rows

        return ambiguities

    def validate_mappings(
        self, spreadsheet_id: str, cached_mappings: Optional[dict] = None
    ) -> AuditReport:
        """
        Validate all cached mappings are still correct.

        Args:
            spreadsheet_id: The spreadsheet to audit
            cached_mappings: Cached mappings to validate (optional)

        Returns:
            AuditReport with validation results
        """
        logger.info(f"Validating mappings for spreadsheet {spreadsheet_id}")

        # This is a placeholder implementation
        # In production, would integrate with MappingManager to validate mappings
        report = AuditReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            spreadsheet_id=spreadsheet_id,
            mappings_checked=0,
            valid_mappings=0,
            invalid_mappings=[],
            warnings=[],
            recommendations=[],
        )

        # Would implement actual validation logic here
        report.recommendations.append(
            "Use /mappings/{spreadsheet_id}/audit endpoint for detailed mapping validation"
        )

        return report
