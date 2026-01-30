"""Formula replacement tools for the agent."""

from typing import Optional

from ..sheets import GoogleSheetsClient
from ..engine import DeterministicReplacer, ReplacementPlan
from ..engine.safety import SafetyValidator
from .registry import Tool, ToolParameter, ToolRegistry


class FormulaTools:
    """Formula manipulation tools that can be registered with the agent."""

    def __init__(self, client: Optional[GoogleSheetsClient] = None):
        self.client = client or GoogleSheetsClient()
        self.replacer = DeterministicReplacer(self.client)

    def register(self, registry: ToolRegistry):
        """Register all formula tools with the registry."""
        registry.register(self._mass_replace_tool())

    def _mass_replace_tool(self) -> Tool:
        """Create the mass_replace tool for deterministic replacements."""

        def handler(
            spreadsheet_id: str,
            search_pattern: str,
            replace_with: str,
            description: str = "",
            target_sheets: Optional[list[str]] = None,
            column_header: Optional[str] = None,
            header_row: int = 1,
            case_sensitive: bool = False,
            is_regex: bool = False,
            dry_run: bool = False,
        ) -> dict:
            """
            Perform deterministic mass replacement of formulas.
            
            This tool bypasses LLM for the actual replacement operation,
            using direct string/regex replacement for efficiency.
            """
            plan = ReplacementPlan(
                action="replace",
                search_pattern=search_pattern,
                replace_with=replace_with,
                target_sheets=target_sheets,
                column_header=column_header,
                header_row=header_row,
                case_sensitive=case_sensitive,
                is_regex=is_regex,
                dry_run=dry_run,
            )

            result = self.replacer.execute_replacement(
                spreadsheet_id=spreadsheet_id,
                plan=plan,
                description=description,
            )

            # Add safety validation to response
            validator = SafetyValidator()
            is_safe, violations = validator.validate_operation(
                cells_affected=result.cells_updated if not dry_run else result.matches_found,
                sheets_affected=len(result.affected_sheets),
            )

            return {
                "success": result.success,
                "matches_found": result.matches_found,
                "cells_updated": result.cells_updated,
                "affected_sheets": result.affected_sheets,
                "preview": result.preview,
                "error": result.error,
                "execution_path": result.execution_path,
                "safety_status": {
                    "is_safe": is_safe,
                    "violations": [
                        {
                            "constraint": v.constraint,
                            "current": v.current_value,
                            "max": v.max_value,
                            "message": v.message
                        }
                        for v in violations
                    ],
                    "requires_preview": validator.requires_preview(result.matches_found)
                },
                "message": (
                    f"{'Preview:' if dry_run else 'Updated'} {result.cells_updated} cells "
                    f"across {len(result.affected_sheets)} sheet(s)"
                    if result.success
                    else f"Error: {result.error}"
                ),
            }

        return Tool(
            name="formula.mass_replace",
            description=(
                "Perform fast, deterministic mass replacement of formula patterns. "
                "Use this for simple find/replace operations like 'VLOOKUP → XLOOKUP' "
                "or '28.6% → 30.0%'. This tool is much faster and cheaper than using LLM "
                "for each formula. Supports exact match and regex patterns. "
                "IMPORTANT: Use this tool instead of manually editing each formula when "
                "you need to do the same replacement across many cells."
            ),
            parameters=[
                ToolParameter(
                    name="spreadsheet_id",
                    type="string",
                    description="The ID of the Google Spreadsheet",
                ),
                ToolParameter(
                    name="search_pattern",
                    type="string",
                    description="The text or regex pattern to search for in formulas",
                ),
                ToolParameter(
                    name="replace_with",
                    type="string",
                    description="The text to replace matches with",
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Human-readable description of this operation",
                    required=False,
                    default="",
                ),
                ToolParameter(
                    name="target_sheets",
                    type="array",
                    description="Optional list of sheet names to limit the replacement (default: all sheets)",
                    required=False,
                ),
                ToolParameter(
                    name="column_header",
                    type="string",
                    description="Optional column header to restrict the replacement to (e.g., 'Abloom'). Logic: Scans headers (row 1) to find the column.",
                    required=False,
                ),
                ToolParameter(
                    name="header_row",
                    type="integer",
                    description="The row number where the header is located (1-based, default: 1). Only used if column_header is set.",
                    required=False,
                    default=1,
                ),
                ToolParameter(
                    name="case_sensitive",
                    type="boolean",
                    description="Whether the search should be case-sensitive (default: false)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="is_regex",
                    type="boolean",
                    description="Whether search_pattern is a regex pattern (default: false)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="If true, only preview changes without applying them (default: false)",
                    required=False,
                    default=False,
                ),
            ],
            handler=handler,
        )
