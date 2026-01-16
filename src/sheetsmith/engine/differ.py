"""Diff generation for formula changes."""

import difflib
from dataclasses import dataclass
from typing import Optional


@dataclass
class FormulaDiff:
    """Represents the difference between two formulas."""

    cell: str
    sheet: str
    old_formula: str
    new_formula: str
    changes: list[dict]  # List of {type, old, new, position}
    similarity: float  # 0.0 to 1.0


@dataclass
class PatchPreview:
    """Preview of changes to be applied."""

    spreadsheet_id: str
    description: str
    diffs: list[FormulaDiff]
    total_cells: int
    summary: str

    def to_diff_string(self) -> str:
        """Generate a human-readable unified diff."""
        lines = [
            f"# Patch: {self.description}",
            f"# Spreadsheet: {self.spreadsheet_id}",
            f"# Total cells to modify: {self.total_cells}",
            "",
        ]

        for diff in self.diffs:
            lines.append(f"--- {diff.sheet}!{diff.cell}")
            lines.append(f"+++ {diff.sheet}!{diff.cell}")

            # Generate unified diff of the formulas
            old_lines = diff.old_formula.split("\n") if diff.old_formula else [""]
            new_lines = diff.new_formula.split("\n") if diff.new_formula else [""]

            for line in difflib.unified_diff(
                old_lines, new_lines, lineterm="", n=0
            ):
                if line.startswith("---") or line.startswith("+++"):
                    continue
                if line.startswith("@@"):
                    continue
                lines.append(line)

            lines.append("")

        return "\n".join(lines)


class FormulaDiffer:
    """Generates diffs between formula versions."""

    def diff_formula(
        self,
        old_formula: str,
        new_formula: str,
        cell: str = "",
        sheet: str = "",
    ) -> FormulaDiff:
        """Generate a diff between two formulas."""
        changes = []

        # Use SequenceMatcher to find changes
        matcher = difflib.SequenceMatcher(None, old_formula, new_formula)
        similarity = matcher.ratio()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                changes.append(
                    {
                        "type": "replace",
                        "old": old_formula[i1:i2],
                        "new": new_formula[j1:j2],
                        "position": i1,
                    }
                )
            elif tag == "delete":
                changes.append(
                    {
                        "type": "delete",
                        "old": old_formula[i1:i2],
                        "new": "",
                        "position": i1,
                    }
                )
            elif tag == "insert":
                changes.append(
                    {
                        "type": "insert",
                        "old": "",
                        "new": new_formula[j1:j2],
                        "position": i1,
                    }
                )

        return FormulaDiff(
            cell=cell,
            sheet=sheet,
            old_formula=old_formula,
            new_formula=new_formula,
            changes=changes,
            similarity=similarity,
        )

    def create_preview(
        self,
        spreadsheet_id: str,
        description: str,
        formula_changes: list[dict],  # List of {sheet, cell, old, new}
    ) -> PatchPreview:
        """Create a preview of all proposed changes."""
        diffs = []

        for change in formula_changes:
            diff = self.diff_formula(
                old_formula=change.get("old", ""),
                new_formula=change.get("new", ""),
                cell=change.get("cell", ""),
                sheet=change.get("sheet", ""),
            )
            diffs.append(diff)

        # Generate summary
        sheets_affected = set(d.sheet for d in diffs)
        summary = (
            f"This patch will modify {len(diffs)} cell(s) "
            f"across {len(sheets_affected)} sheet(s)."
        )

        return PatchPreview(
            spreadsheet_id=spreadsheet_id,
            description=description,
            diffs=diffs,
            total_cells=len(diffs),
            summary=summary,
        )

    def find_targeted_replacement(
        self,
        formula: str,
        old_value: str,
        new_value: str,
        context_pattern: Optional[str] = None,
    ) -> Optional[str]:
        """
        Replace a specific value in a formula while preserving structure.

        If context_pattern is provided, only replace within that context.
        """
        import re

        if context_pattern:
            # Find the context and replace within it
            pattern = re.compile(context_pattern, re.IGNORECASE | re.DOTALL)
            match = pattern.search(formula)
            if match:
                context = match.group(0)
                new_context = context.replace(old_value, new_value)
                return formula[: match.start()] + new_context + formula[match.end() :]
            return None

        # Simple replacement
        if old_value in formula:
            return formula.replace(old_value, new_value)

        return None

    def generate_replacement_patch(
        self,
        spreadsheet_id: str,
        matches: list[dict],  # FormulaMatch-like dicts
        old_value: str,
        new_value: str,
        description: str,
        context_pattern: Optional[str] = None,
    ) -> PatchPreview:
        """Generate a patch for replacing a value across multiple formulas."""
        formula_changes = []

        for match in matches:
            old_formula = match.get("formula", "")
            new_formula = self.find_targeted_replacement(
                old_formula, old_value, new_value, context_pattern
            )

            if new_formula and new_formula != old_formula:
                formula_changes.append(
                    {
                        "sheet": match.get("sheet", ""),
                        "cell": match.get("cell", ""),
                        "old": old_formula,
                        "new": new_formula,
                    }
                )

        return self.create_preview(spreadsheet_id, description, formula_changes)
