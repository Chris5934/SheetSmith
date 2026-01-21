"""Mapping validation logic for header-based mappings."""

import logging
from typing import Optional

from ..sheets import GoogleSheetsClient
from .models import (
    ColumnMapping,
    CellMapping,
    MappingStatus,
    ValidationResult,
    ColumnCandidate,
)

logger = logging.getLogger(__name__)


class MappingValidator:
    """Validates that mappings are still accurate."""

    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client

    async def validate_column_mapping(self, mapping: ColumnMapping) -> ValidationResult:
        """
        Validate that a column mapping is still accurate.

        Checks:
        1. Header still exists
        2. Header is in expected position
        3. No duplicate headers exist

        Returns ValidationResult with status and any required actions.
        """
        try:
            # Read the header row to find the header
            header_candidates = await self._find_header_in_sheet(
                mapping.spreadsheet_id,
                mapping.sheet_name,
                mapping.header_text,
                expected_row=mapping.header_row,
            )

            if len(header_candidates) == 0:
                # Header not found
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.MISSING,
                    message=f"Header '{mapping.header_text}' not found in sheet '{mapping.sheet_name}'",
                    old_column_letter=mapping.column_letter,
                )

            if len(header_candidates) > 1:
                # Multiple headers found - ambiguous
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.AMBIGUOUS,
                    message=f"Multiple columns found with header '{mapping.header_text}'",
                    requires_disambiguation=True,
                    candidates=header_candidates,
                )

            # Single header found
            candidate = header_candidates[0]

            if candidate.column_letter == mapping.column_letter:
                # Header is in expected position
                return ValidationResult(
                    is_valid=True,
                    status=MappingStatus.VALID,
                    message=f"Header '{mapping.header_text}' is valid at column {mapping.column_letter}",
                )
            else:
                # Header moved to a different column
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.MOVED,
                    message=f"Header '{mapping.header_text}' moved from column "
                    f"{mapping.column_letter} to {candidate.column_letter}",
                    old_column_letter=mapping.column_letter,
                    new_column_letter=candidate.column_letter,
                )

        except Exception as e:
            logger.error(f"Error validating column mapping: {e}")
            return ValidationResult(
                is_valid=False,
                status=MappingStatus.MISSING,
                message=f"Error validating mapping: {str(e)}",
            )

    async def validate_cell_mapping(self, mapping: CellMapping) -> ValidationResult:
        """
        Validate that a cell mapping is still accurate.

        Checks:
        1. Column header still exists
        2. Row label still exists
        3. Intersection cell is still valid

        Returns ValidationResult with status and any required actions.
        """
        try:
            # First validate the column header
            header_candidates = await self._find_header_in_sheet(
                mapping.spreadsheet_id,
                mapping.sheet_name,
                mapping.column_header,
                expected_row=0,  # Assume headers are in first row
            )

            if len(header_candidates) == 0:
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.MISSING,
                    message=f"Column header '{mapping.column_header}' not found",
                    old_column_letter=mapping.column_letter,
                )

            if len(header_candidates) > 1:
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.AMBIGUOUS,
                    message=f"Multiple columns found with header '{mapping.column_header}'",
                    requires_disambiguation=True,
                    candidates=header_candidates,
                )

            # Then validate the row label
            row_index = await self._find_row_label_in_sheet(
                mapping.spreadsheet_id,
                mapping.sheet_name,
                mapping.row_label,
            )

            if row_index is None:
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.MISSING,
                    message=f"Row label '{mapping.row_label}' not found",
                )

            # Check if the cell address is still correct
            header_candidate = header_candidates[0]
            new_cell_address = f"{header_candidate.column_letter}{row_index + 1}"

            if new_cell_address == mapping.cell_address:
                return ValidationResult(
                    is_valid=True,
                    status=MappingStatus.VALID,
                    message=f"Cell mapping '{mapping.column_header} × {mapping.row_label}' "
                    f"is valid at {mapping.cell_address}",
                )
            else:
                return ValidationResult(
                    is_valid=False,
                    status=MappingStatus.MOVED,
                    message=f"Cell mapping moved from {mapping.cell_address} to {new_cell_address}",
                    old_column_letter=mapping.cell_address,
                    new_column_letter=new_cell_address,
                )

        except Exception as e:
            logger.error(f"Error validating cell mapping: {e}")
            return ValidationResult(
                is_valid=False,
                status=MappingStatus.MISSING,
                message=f"Error validating mapping: {str(e)}",
            )

    async def _find_header_in_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        header_text: str,
        expected_row: int = 0,
    ) -> list[ColumnCandidate]:
        """
        Find all occurrences of a header in a sheet.

        Returns list of ColumnCandidate objects for each match.
        """
        # Read the header row (or multiple rows to search)
        range_notation = f"{sheet_name}!A1:ZZ10"  # Read first 10 rows to find header

        try:
            result = self.sheets_client.read_range(
                spreadsheet_id, range_notation, include_formulas=False
            )

            candidates = []

            # Search through the cells to find matching headers
            for cell in result.cells:
                if cell.value and str(cell.value).strip() == header_text:
                    # Found a matching header
                    # Extract column letter from cell address (e.g., "A1" -> "A")
                    col_letter = "".join(c for c in cell.cell if c.isalpha())
                    row_num = int("".join(c for c in cell.cell if c.isdigit()))

                    # Get column index (A=0, B=1, etc.)
                    col_index = self._column_letter_to_index(col_letter)

                    # Get sample values from this column
                    sample_values = await self._get_column_sample_values(
                        result, col_index, start_row=row_num
                    )

                    # Get adjacent headers
                    adjacent_headers = await self._get_adjacent_headers(
                        result, col_index, row_num - 1
                    )

                    candidates.append(
                        ColumnCandidate(
                            column_letter=col_letter,
                            column_index=col_index,
                            header_row=row_num - 1,  # 0-based
                            sample_values=sample_values,
                            adjacent_headers=adjacent_headers,
                        )
                    )

            return candidates

        except Exception as e:
            logger.error(f"Error finding header in sheet: {e}")
            return []

    async def _find_row_label_in_sheet(
        self, spreadsheet_id: str, sheet_name: str, row_label: str
    ) -> Optional[int]:
        """
        Find a row by its label in the first column.

        Returns 0-based row index, or None if not found.
        """
        # Read the first column to find the row label
        range_notation = f"{sheet_name}!A:A"

        try:
            result = self.sheets_client.read_range(
                spreadsheet_id, range_notation, include_formulas=False
            )

            for cell in result.cells:
                if cell.value and str(cell.value).strip() == row_label:
                    # Extract row number from cell address
                    row_num = int("".join(c for c in cell.cell if c.isdigit()))
                    return row_num - 1  # Return 0-based index

            return None

        except Exception as e:
            logger.error(f"Error finding row label in sheet: {e}")
            return None

    async def _get_column_sample_values(
        self, result, col_index: int, start_row: int, max_samples: int = 5
    ) -> list[str]:
        """Get sample values from a column."""
        samples = []
        for cell in result.cells:
            # Extract row number from cell address
            row_num = int("".join(c for c in cell.cell if c.isdigit()))
            # Extract column letter
            col_letter = "".join(c for c in cell.cell if c.isalpha())
            cell_col_index = self._column_letter_to_index(col_letter)

            if cell_col_index == col_index and row_num > start_row:
                if cell.value:
                    samples.append(str(cell.value))
                if len(samples) >= max_samples:
                    break

        return samples

    async def _get_adjacent_headers(
        self, result, col_index: int, header_row: int
    ) -> dict[str, Optional[str]]:
        """Get headers from adjacent columns."""
        adjacent = {"left": None, "right": None}

        for cell in result.cells:
            row_num = int("".join(c for c in cell.cell if c.isdigit())) - 1  # 0-based
            col_letter = "".join(c for c in cell.cell if c.isalpha())
            cell_col_index = self._column_letter_to_index(col_letter)

            if row_num == header_row:
                if cell_col_index == col_index - 1:
                    adjacent["left"] = str(cell.value) if cell.value else None
                elif cell_col_index == col_index + 1:
                    adjacent["right"] = str(cell.value) if cell.value else None

        return adjacent

    @staticmethod
    def _column_letter_to_index(col_letter: str) -> int:
        """Convert column letter to 0-based index (A=0, B=1, etc.)."""
        index = 0
        for char in col_letter:
            index = index * 26 + (ord(char.upper()) - ord("A") + 1)
        return index - 1

    @staticmethod
    def _column_index_to_letter(col_index: int) -> str:
        """Convert 0-based column index to letter (0=A, 1=B, etc.)."""
        letter = ""
        col_index += 1  # Convert to 1-based
        while col_index > 0:
            col_index -= 1
            letter = chr(col_index % 26 + ord("A")) + letter
            col_index //= 26
        return letter
