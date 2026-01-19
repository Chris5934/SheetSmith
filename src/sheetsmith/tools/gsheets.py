"""Google Sheets tools for the agent."""

from typing import Optional

from ..sheets import GoogleSheetsClient, BatchUpdate
from .registry import Tool, ToolParameter, ToolRegistry


class GSheetsTools:
    """Google Sheets tools that can be registered with the agent."""

    def __init__(self, client: Optional[GoogleSheetsClient] = None):
        self.client = client or GoogleSheetsClient()

    def register(self, registry: ToolRegistry):
        """Register all Google Sheets tools with the registry."""
        registry.register(self._read_range_tool())
        registry.register(self._search_formulas_tool())
        registry.register(self._batch_update_tool())
        registry.register(self._get_spreadsheet_info_tool())

    def _read_range_tool(self) -> Tool:
        """Create the read_range tool."""

        def handler(
            spreadsheet_id: str,
            range_notation: str,
            include_formulas: bool = True,
        ) -> dict:
            result = self.client.read_range(spreadsheet_id, range_notation, include_formulas)
            return {
                "spreadsheet_id": result.spreadsheet_id,
                "sheet_name": result.sheet_name,
                "range": result.range_notation,
                "cell_count": len(result.cells),
                "cells": [
                    {
                        "cell": c.cell,
                        "value": c.value,
                        "formula": c.formula,
                    }
                    for c in result.cells
                ],
                "formulas_found": len(result.formulas),
            }

        return Tool(
            name="gsheets.read_range",
            description="Read values and formulas from a range in a Google Sheet. "
            "Use this to inspect cell contents, understand formula structure, "
            "or gather data for analysis.",
            parameters=[
                ToolParameter(
                    name="spreadsheet_id",
                    type="string",
                    description="The ID of the Google Spreadsheet (from the URL)",
                ),
                ToolParameter(
                    name="range_notation",
                    type="string",
                    description="The range to read in A1 notation (e.g., 'Sheet1!A1:C10')",
                ),
                ToolParameter(
                    name="include_formulas",
                    type="boolean",
                    description="Whether to include formula text (default: true)",
                    required=False,
                    default=True,
                ),
            ],
            handler=handler,
        )

    def _search_formulas_tool(self) -> Tool:
        """Create the search_formulas tool."""

        def handler(
            spreadsheet_id: str,
            pattern: str,
            sheet_names: Optional[list[str]] = None,
            case_sensitive: bool = False,
        ) -> dict:
            matches = self.client.search_formulas(
                spreadsheet_id, pattern, sheet_names, case_sensitive
            )
            return {
                "spreadsheet_id": spreadsheet_id,
                "pattern": pattern,
                "match_count": len(matches),
                "matches": [
                    {
                        "sheet": m.sheet_name,
                        "cell": m.cell,
                        "formula": m.formula,
                        "matched_text": m.matched_text,
                    }
                    for m in matches
                ],
            }

        return Tool(
            name="gsheets.search_formulas",
            description="Search for formulas matching a regex pattern across all sheets "
            "or specific sheets in a spreadsheet. Use this to find all instances "
            "of shared logic, specific functions, or patterns that need updating.",
            parameters=[
                ToolParameter(
                    name="spreadsheet_id",
                    type="string",
                    description="The ID of the Google Spreadsheet",
                ),
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Regex pattern to search for in formulas",
                ),
                ToolParameter(
                    name="sheet_names",
                    type="array",
                    description="Optional list of sheet names to search (default: all sheets)",
                    required=False,
                ),
                ToolParameter(
                    name="case_sensitive",
                    type="boolean",
                    description="Whether the search should be case-sensitive (default: false)",
                    required=False,
                    default=False,
                ),
            ],
            handler=handler,
        )

    def _batch_update_tool(self) -> Tool:
        """Create the batch_update tool."""

        def handler(
            spreadsheet_id: str,
            updates: list[dict],
            description: str = "",
        ) -> dict:
            batch = BatchUpdate(
                spreadsheet_id=spreadsheet_id,
                description=description,
            )
            for update in updates:
                batch.add_update(
                    sheet_name=update["sheet_name"],
                    cell=update["cell"],
                    new_value=update.get("new_value"),
                    new_formula=update.get("new_formula"),
                )

            result = self.client.batch_update(batch)
            return {
                "success": result.success,
                "updated_cells": result.updated_cells,
                "errors": result.errors,
            }

        return Tool(
            name="gsheets.batch_update",
            description="Apply multiple cell updates to a spreadsheet in a single operation. "
            "Use this to safely apply formula changes across multiple cells/sheets. "
            "Each update can specify either a new value or a new formula.",
            parameters=[
                ToolParameter(
                    name="spreadsheet_id",
                    type="string",
                    description="The ID of the Google Spreadsheet",
                ),
                ToolParameter(
                    name="updates",
                    type="array",
                    description="List of updates. Each update should have: sheet_name, cell, "
                    "and either new_value or new_formula",
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Description of what this batch update does",
                    required=False,
                    default="",
                ),
            ],
            handler=handler,
        )

    def _get_spreadsheet_info_tool(self) -> Tool:
        """Create the get_spreadsheet_info tool."""

        def handler(spreadsheet_id: str) -> dict:
            return self.client.get_spreadsheet_info(spreadsheet_id)

        return Tool(
            name="gsheets.get_info",
            description="Get information about a spreadsheet including its title, "
            "list of sheets, and their dimensions. Use this to understand "
            "the structure of a spreadsheet before reading or modifying it.",
            parameters=[
                ToolParameter(
                    name="spreadsheet_id",
                    type="string",
                    description="The ID of the Google Spreadsheet",
                ),
            ],
            handler=handler,
        )
