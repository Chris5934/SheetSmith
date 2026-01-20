"""Deterministic formula replacement engine for mass operations."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ..sheets import GoogleSheetsClient, BatchUpdate
from ..sheets.models import FormulaMatch

logger = logging.getLogger(__name__)


@dataclass
class ReplacementPlan:
    """Plan for deterministic formula replacement."""

    action: str  # "replace", "regex_replace"
    search_pattern: str  # What to search for
    replace_with: str  # What to replace it with
    target_sheets: Optional[list[str]] = None  # Specific sheets, or None for all
    case_sensitive: bool = False
    is_regex: bool = False
    dry_run: bool = False


@dataclass
class ReplacementResult:
    """Result of a deterministic replacement operation."""

    success: bool
    matches_found: int
    cells_updated: int
    affected_sheets: list[str]
    preview: Optional[str] = None  # Diff preview if dry_run=True
    error: Optional[str] = None
    execution_path: str = "deterministic"  # Track if LLM was used


class DeterministicReplacer:
    """
    Performs deterministic formula replacements without LLM involvement.

    This class handles simple find/replace operations at scale, reserving
    LLM usage only for planning and complex edge cases.
    """

    def __init__(self, sheets_client: Optional[GoogleSheetsClient] = None):
        self.sheets_client = sheets_client or GoogleSheetsClient()

    def execute_replacement(
        self,
        spreadsheet_id: str,
        plan: ReplacementPlan,
        description: str = "",
    ) -> ReplacementResult:
        """
        Execute a deterministic replacement based on a plan.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            plan: The replacement plan to execute
            description: Human-readable description of the operation

        Returns:
            ReplacementResult with details of the operation
        """
        try:
            logger.info(
                f"Starting deterministic replacement: {plan.action} "
                f"(pattern: '{plan.search_pattern}', replace: '{plan.replace_with}')"
            )

            # Step 1: Search for matching formulas
            matches = self._search_formulas(
                spreadsheet_id=spreadsheet_id,
                pattern=plan.search_pattern,
                sheet_names=plan.target_sheets,
                case_sensitive=plan.case_sensitive,
                is_regex=plan.is_regex,
            )

            if not matches:
                logger.info("No matching formulas found")
                return ReplacementResult(
                    success=True,
                    matches_found=0,
                    cells_updated=0,
                    affected_sheets=[],
                    preview=None,
                )

            logger.info(f"Found {len(matches)} matching formulas")

            # Step 2: Generate replacements
            replacements = self._generate_replacements(matches, plan)

            if not replacements:
                logger.warning("No valid replacements generated")
                return ReplacementResult(
                    success=False,
                    matches_found=len(matches),
                    cells_updated=0,
                    affected_sheets=[],
                    error="No valid replacements could be generated",
                )

            # Step 3: Generate preview
            affected_sheets = list(set(r["sheet"] for r in replacements))
            preview = self._generate_preview(replacements) if plan.dry_run else None

            # Step 4: Apply changes (unless dry_run)
            cells_updated = 0
            if not plan.dry_run:
                cells_updated = self._apply_replacements(
                    spreadsheet_id=spreadsheet_id,
                    replacements=replacements,
                    description=description
                    or f"Mass replace: {plan.search_pattern} → {plan.replace_with}",
                )

            return ReplacementResult(
                success=True,
                matches_found=len(matches),
                cells_updated=cells_updated,
                affected_sheets=affected_sheets,
                preview=preview,
            )

        except Exception as e:
            logger.error(f"Deterministic replacement failed: {e}")
            return ReplacementResult(
                success=False,
                matches_found=0,
                cells_updated=0,
                affected_sheets=[],
                error=str(e),
            )

    def _search_formulas(
        self,
        spreadsheet_id: str,
        pattern: str,
        sheet_names: Optional[list[str]],
        case_sensitive: bool,
        is_regex: bool,
    ) -> list[FormulaMatch]:
        """Search for formulas matching the pattern."""
        # For exact matches, escape regex special characters
        search_pattern = pattern if is_regex else re.escape(pattern)

        return self.sheets_client.search_formulas(
            spreadsheet_id=spreadsheet_id,
            pattern=search_pattern,
            sheet_names=sheet_names,
            case_sensitive=case_sensitive,
        )

    def _generate_replacements(
        self,
        matches: list[FormulaMatch],
        plan: ReplacementPlan,
    ) -> list[dict]:
        """
        Generate replacement formulas based on the plan.

        Returns list of dicts with: sheet, cell, old_formula, new_formula
        """
        replacements = []

        for match in matches:
            old_formula = match.formula
            new_formula = self._apply_replacement(old_formula, plan)

            # Only include if the formula actually changed
            if new_formula and new_formula != old_formula:
                replacements.append(
                    {
                        "sheet": match.sheet_name,
                        "cell": match.cell,
                        "old_formula": old_formula,
                        "new_formula": new_formula,
                    }
                )

        return replacements

    def _apply_replacement(self, formula: str, plan: ReplacementPlan) -> str:
        """Apply the replacement to a single formula."""
        if plan.is_regex:
            # Regex replacement
            flags = 0 if plan.case_sensitive else re.IGNORECASE
            try:
                new_formula = re.sub(
                    plan.search_pattern,
                    plan.replace_with,
                    formula,
                    flags=flags,
                )
                return new_formula
            except re.error as e:
                logger.error(f"Regex error: {e}")
                return formula
        else:
            # Simple string replacement
            if plan.case_sensitive:
                return formula.replace(plan.search_pattern, plan.replace_with)
            else:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(plan.search_pattern), re.IGNORECASE)
                return pattern.sub(plan.replace_with, formula)

    def _generate_preview(self, replacements: list[dict]) -> str:
        """Generate a preview of the changes."""
        lines = [
            "# Preview of Deterministic Replacements",
            f"# Total cells to modify: {len(replacements)}",
            "",
        ]

        # Show first few examples
        max_preview = 10
        for i, rep in enumerate(replacements[:max_preview]):
            lines.append(f"--- {rep['sheet']}!{rep['cell']}")
            lines.append(f"- {rep['old_formula']}")
            lines.append(f"+ {rep['new_formula']}")
            lines.append("")

        if len(replacements) > max_preview:
            lines.append(f"... and {len(replacements) - max_preview} more changes")

        return "\n".join(lines)

    def _apply_replacements(
        self,
        spreadsheet_id: str,
        replacements: list[dict],
        description: str,
    ) -> int:
        """Apply the replacements using batch_update."""
        batch = BatchUpdate(
            spreadsheet_id=spreadsheet_id,
            description=description,
        )

        for rep in replacements:
            batch.add_update(
                sheet_name=rep["sheet"],
                cell=rep["cell"],
                new_formula=rep["new_formula"],
            )

        result = self.sheets_client.batch_update(batch)

        if not result.success:
            raise RuntimeError(f"Batch update failed: {result.errors}")

        logger.info(f"Successfully updated {result.updated_cells} cells")
        return result.updated_cells

    @staticmethod
    def can_handle_deterministically(request: str) -> bool:
        """
        Determine if a request can be handled deterministically.

        Returns True for simple find/replace operations like:
        - "Replace VLOOKUP with XLOOKUP"
        - "Update 28.6% to 30.0%"
        - "Change 'Corruption' to 'Enhanced Corruption'"

        Returns False for complex operations that need LLM reasoning.
        """
        request_lower = request.lower()

        # Keywords indicating simple replacement
        simple_keywords = [
            "replace",
            "change",
            "update",
            "swap",
            "substitute",
        ]

        # Keywords indicating complexity (needs LLM)
        complex_keywords = [
            "refactor",
            "restructure",
            "optimize",
            "fix logic",
            "correct formula",
            "adjust references",
            "recalculate",
        ]

        # Check for complex indicators first
        if any(keyword in request_lower for keyword in complex_keywords):
            return False

        # Check for simple indicators
        if any(keyword in request_lower for keyword in simple_keywords):
            # Additional check: contains clear "X to Y" or "X with Y" pattern
            if " to " in request_lower or " with " in request_lower:
                return True

        return False

    @staticmethod
    def parse_simple_replacement(request: str) -> Optional[ReplacementPlan]:
        """
        Parse a simple replacement request into a ReplacementPlan.

        Example inputs:
        - "Replace VLOOKUP with XLOOKUP in Sheet1"
        - "Update 28.6% to 30.0%"
        - "Change all references to OldSheet with NewSheet"

        Returns None if the request cannot be parsed as a simple replacement.
        """
        # Try to extract pattern: "replace X with Y" or "change X to Y"
        # Use non-greedy matching and better boundaries to avoid capturing too much
        patterns = [
            r"(?i)replace\s+['\"]?([^'\"]+?)['\"]?\s+(?:with|to)\s+['\"]?([^'\"]+?)['\"]?(?:\s+in\s+(.+?))?(?:\s*$)",
            r"(?i)change\s+(?:all\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:with|to)\s+['\"]?([^'\"]+?)['\"]?(?:\s+in\s+(.+?))?(?:\s*$)",
            r"(?i)update\s+['\"]?([^'\"]+?)['\"]?\s+to\s+['\"]?([^'\"]+?)['\"]?(?:\s+in\s+(.+?))?(?:\s*$)",
            r"(?i)swap\s+['\"]?([^'\"]+?)['\"]?\s+(?:with|for)\s+['\"]?([^'\"]+?)['\"]?(?:\s+in\s+(.+?))?(?:\s*$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, request)
            if match:
                # Preserve original case
                search_term = match.group(1).strip().strip("'\"")
                replace_term = match.group(2).strip().strip("'\"")
                target = match.group(3).strip() if match.group(3) else None

                # Parse target sheets - look for "SheetX" pattern, not just numbers
                target_sheets = None
                if target:
                    # Extract sheet names: look for word after "sheet" or quoted names
                    sheets = re.findall(
                        r"(?:sheet\s+)?([A-Za-z][A-Za-z0-9]*)", target, re.IGNORECASE
                    )
                    if sheets:
                        # Filter out common words like "and", "in"
                        sheets = [
                            s for s in sheets if s.lower() not in ("and", "in", "or", "sheet")
                        ]
                        if sheets:
                            target_sheets = sheets

                return ReplacementPlan(
                    action="replace",
                    search_pattern=search_term,
                    replace_with=replace_term,
                    target_sheets=target_sheets,
                    case_sensitive=False,
                    is_regex=False,
                    dry_run=False,
                )

        return None
