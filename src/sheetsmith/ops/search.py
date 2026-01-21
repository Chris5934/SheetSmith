"""Search logic for deterministic operations."""

import re
import logging
import time
from typing import Optional
from ..sheets import GoogleSheetsClient
from ..sheets.client import parse_cell_notation
from .models import SearchCriteria, CellMatch, SearchResult

logger = logging.getLogger(__name__)


class CellSearchEngine:
    """Engine for searching cells based on various criteria."""

    def __init__(self, sheets_client: Optional[GoogleSheetsClient] = None):
        self.sheets_client = sheets_client or GoogleSheetsClient()

    def search(
        self,
        spreadsheet_id: str,
        criteria: SearchCriteria,
        limit: int = 1000,
    ) -> SearchResult:
        """
        Search for cells matching the given criteria.
        
        Args:
            spreadsheet_id: The spreadsheet to search
            criteria: Search criteria
            limit: Maximum number of matches to return
            
        Returns:
            SearchResult with matching cells
        """
        start_time = time.time()
        matches: list[CellMatch] = []
        
        # Get spreadsheet info
        info = self.sheets_client.get_spreadsheet_info(spreadsheet_id)
        sheets_to_search = criteria.sheet_names or [s["title"] for s in info["sheets"]]
        
        logger.info(f"Searching {len(sheets_to_search)} sheets with criteria: {criteria}")
        
        for sheet in info["sheets"]:
            if sheet["title"] not in sheets_to_search:
                continue
            
            if len(matches) >= limit:
                logger.info(f"Reached limit of {limit} matches")
                break
            
            # Search this sheet
            sheet_matches = self._search_sheet(
                spreadsheet_id=spreadsheet_id,
                sheet=sheet,
                criteria=criteria,
                limit=limit - len(matches),
            )
            matches.extend(sheet_matches)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return SearchResult(
            matches=matches,
            total_count=len(matches),
            searched_sheets=sheets_to_search,
            execution_time_ms=execution_time,
        )

    def _search_sheet(
        self,
        spreadsheet_id: str,
        sheet: dict,
        criteria: SearchCriteria,
        limit: int,
    ) -> list[CellMatch]:
        """Search a single sheet for matching cells."""
        from ..sheets.client import index_to_col_letter
        
        matches: list[CellMatch] = []
        sheet_name = sheet["title"]
        
        # Read the entire sheet with formulas
        range_notation = f"'{sheet_name}'!A1:{index_to_col_letter(sheet['col_count'] - 1)}{sheet['row_count']}"
        
        try:
            sheet_data = self.sheets_client.read_range(
                spreadsheet_id, range_notation, include_formulas=True
            )
        except Exception as e:
            logger.warning(f"Failed to read sheet '{sheet_name}': {e}")
            return matches
        
        # Extract headers from first row if needed
        headers = self._extract_headers(sheet_data.cells)
        
        # Search each cell
        for cell in sheet_data.cells:
            if len(matches) >= limit:
                break
            
            if self._matches_criteria(cell, headers, criteria):
                # Get header for this cell
                header = headers.get(cell.col)
                
                # Get row label (first column value of this row)
                row_label = self._get_row_label(sheet_data.cells, cell.row)
                
                matches.append(
                    CellMatch(
                        spreadsheet_id=spreadsheet_id,
                        sheet_name=sheet_name,
                        cell=cell.cell,
                        row=cell.row,
                        col=cell.col,
                        header=header,
                        row_label=row_label,
                        value=cell.value,
                        formula=cell.formula,
                    )
                )
        
        logger.info(f"Found {len(matches)} matches in sheet '{sheet_name}'")
        return matches

    def _extract_headers(self, cells: list) -> dict[int, str]:
        """
        Extract column headers from the first row.
        
        Returns:
            Dictionary mapping column index to header text
        """
        headers = {}
        
        # Find all cells in row 1
        for cell in cells:
            if cell.row == 1 and cell.value:
                headers[cell.col] = str(cell.value)
        
        return headers

    def _get_row_label(self, cells: list, row: int) -> Optional[str]:
        """Get the row label (first column value) for a given row."""
        for cell in cells:
            if cell.row == row and cell.col == 0:  # Column A (index 0)
                return str(cell.value) if cell.value else None
        return None

    def _matches_criteria(self, cell, headers: dict, criteria: SearchCriteria) -> bool:
        """Check if a cell matches the search criteria."""
        
        # Skip header row (row 1) in value/formula searches
        if criteria.formula_pattern or criteria.value_pattern:
            if cell.row == 1:
                return False
        
        # Check header text filter
        if criteria.header_text:
            header = headers.get(cell.col)
            if not header:
                return False
            
            if criteria.case_sensitive:
                if criteria.header_text != header:
                    return False
            else:
                if criteria.header_text.lower() != header.lower():
                    return False
        
        # Check formula pattern
        if criteria.formula_pattern:
            if not cell.formula:
                return False
            
            try:
                flags = 0 if criteria.case_sensitive else re.IGNORECASE
                if criteria.is_regex:
                    if not re.search(criteria.formula_pattern, cell.formula, flags):
                        return False
                else:
                    # Simple substring search
                    if criteria.case_sensitive:
                        if criteria.formula_pattern not in cell.formula:
                            return False
                    else:
                        if criteria.formula_pattern.lower() not in cell.formula.lower():
                            return False
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {e}")
                return False
        
        # Check value pattern
        if criteria.value_pattern:
            if cell.value is None:
                return False
            
            value_str = str(cell.value)
            
            try:
                flags = 0 if criteria.case_sensitive else re.IGNORECASE
                if criteria.is_regex:
                    if not re.search(criteria.value_pattern, value_str, flags):
                        return False
                else:
                    # Simple substring search
                    if criteria.case_sensitive:
                        if criteria.value_pattern not in value_str:
                            return False
                    else:
                        if criteria.value_pattern.lower() not in value_str.lower():
                            return False
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {e}")
                return False
        
        # Check row label filter
        if criteria.row_label:
            # This is handled at a higher level since we need to look at column A
            pass
        
        return True
