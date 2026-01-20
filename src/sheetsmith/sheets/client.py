"""Google Sheets API client."""

import logging
import re
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import settings
from .models import (
    CellData,
    SheetRange,
    FormulaMatch,
    BatchUpdate,
    UpdateResult,
    CellUpdate,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def col_letter_to_index(col: str) -> int:
    """Convert column letter(s) to 0-based index. A=0, B=1, ..., Z=25, AA=26, etc."""
    result = 0
    for char in col.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def index_to_col_letter(index: int) -> str:
    """Convert 0-based index to column letter(s)."""
    result = ""
    index += 1
    while index > 0:
        index -= 1
        result = chr(ord("A") + (index % 26)) + result
        index //= 26
    return result


def parse_cell_notation(cell: str) -> tuple[str, int]:
    """Parse A1 notation into column letters and row number."""
    match = re.match(r"([A-Za-z]+)(\d+)", cell)
    if not match:
        raise ValueError(f"Invalid cell notation: {cell}")
    return match.group(1).upper(), int(match.group(2))


class GoogleSheetsClient:
    """Client for interacting with Google Sheets API."""

    def __init__(self):
        self._service = None
        self._credentials = None

    def _get_credentials(self) -> Credentials:
        """Get or refresh OAuth2 credentials."""
        creds = None

        if settings.google_token_path.exists():
            creds = Credentials.from_authorized_user_file(str(settings.google_token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not settings.google_credentials_path.exists():
                    raise FileNotFoundError(
                        f"Google credentials file not found at {settings.google_credentials_path}. "
                        "Please download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(settings.google_credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            settings.google_token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings.google_token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    @property
    def service(self):
        """Get or create the Sheets API service."""
        if self._service is None:
            self._credentials = self._get_credentials()
            self._service = build("sheets", "v4", credentials=self._credentials)
        return self._service

    def get_spreadsheet_info(self, spreadsheet_id: str) -> dict:
        """Get basic information about a spreadsheet."""
        try:
            result = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return {
                "id": result["spreadsheetId"],
                "title": result["properties"]["title"],
                "sheets": [
                    {
                        "id": sheet["properties"]["sheetId"],
                        "title": sheet["properties"]["title"],
                        "row_count": sheet["properties"]["gridProperties"]["rowCount"],
                        "col_count": sheet["properties"]["gridProperties"]["columnCount"],
                    }
                    for sheet in result.get("sheets", [])
                ],
            }
        except HttpError as e:
            raise RuntimeError(f"Failed to get spreadsheet info: {e}")

    def read_range(
        self,
        spreadsheet_id: str,
        range_notation: str,
        include_formulas: bool = True,
    ) -> SheetRange:
        """Read values and optionally formulas from a range."""
        try:
            # Parse sheet name from range
            if "!" in range_notation:
                sheet_name = range_notation.split("!")[0].strip("'")
            else:
                sheet_name = "Sheet1"

            # Get values
            values_result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_notation)
                .execute()
            )
            values = values_result.get("values", [])

            # Get formulas if requested
            formulas = []
            if include_formulas:
                formulas_result = (
                    self.service.spreadsheets()
                    .values()
                    .get(
                        spreadsheetId=spreadsheet_id,
                        range=range_notation,
                        valueRenderOption="FORMULA",
                    )
                    .execute()
                )
                formulas = formulas_result.get("values", [])

            # Parse the starting cell from range
            range_part = range_notation.split("!")[-1]
            start_cell = range_part.split(":")[0]
            start_col, start_row = parse_cell_notation(start_cell)
            start_col_idx = col_letter_to_index(start_col)

            # Build cell data
            cells = []
            for row_idx, row_values in enumerate(values):
                for col_idx, value in enumerate(row_values):
                    abs_row = start_row + row_idx
                    abs_col = start_col_idx + col_idx
                    cell_notation = f"{index_to_col_letter(abs_col)}{abs_row}"

                    formula = None
                    if formulas and row_idx < len(formulas) and col_idx < len(formulas[row_idx]):
                        formula_value = formulas[row_idx][col_idx]
                        if isinstance(formula_value, str) and formula_value.startswith("="):
                            formula = formula_value

                    cells.append(
                        CellData(
                            sheet_name=sheet_name,
                            cell=cell_notation,
                            row=abs_row,
                            col=abs_col,
                            value=value,
                            formula=formula,
                        )
                    )

            return SheetRange(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                range_notation=range_notation,
                cells=cells,
            )

        except HttpError as e:
            raise RuntimeError(f"Failed to read range: {e}")

    def search_formulas(
        self,
        spreadsheet_id: str,
        pattern: str,
        sheet_names: Optional[list[str]] = None,
        case_sensitive: bool = False,
    ) -> list[FormulaMatch]:
        """Search for formulas matching a pattern across sheets."""
        matches = []

        # Get spreadsheet info to know which sheets to search
        info = self.get_spreadsheet_info(spreadsheet_id)
        sheets_to_search = sheet_names or [s["title"] for s in info["sheets"]]

        regex_flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled_pattern = re.compile(pattern, regex_flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        for sheet in info["sheets"]:
            if sheet["title"] not in sheets_to_search:
                continue

            logger.info(
                f"Scanning sheet '{sheet['title']}' - dimensions: "
                f"{sheet['row_count']}x{sheet['col_count']}"
            )

            # Read the entire sheet
            range_notation = f"'{sheet['title']}'!A1:{index_to_col_letter(sheet['col_count'] - 1)}{sheet['row_count']}"
            logger.debug(f"Range notation: {range_notation}")

            try:
                sheet_data = self.read_range(spreadsheet_id, range_notation, include_formulas=True)
            except Exception:
                continue

            for cell in sheet_data.formulas:
                if cell.formula:
                    match = compiled_pattern.search(cell.formula)
                    if match:
                        matches.append(
                            FormulaMatch(
                                spreadsheet_id=spreadsheet_id,
                                sheet_name=sheet["title"],
                                cell=cell.cell,
                                row=cell.row,
                                col=cell.col,
                                formula=cell.formula,
                                matched_text=match.group(0),
                            )
                        )

            sheet_matches = [m for m in matches if m.sheet_name == sheet["title"]]
            logger.info(f"Found {len(sheet_matches)} matching formulas in sheet '{sheet['title']}'")

        return matches

    def batch_update(self, batch: BatchUpdate) -> UpdateResult:
        """Apply a batch of updates to a spreadsheet."""
        if not batch.updates:
            return UpdateResult(
                success=True,
                spreadsheet_id=batch.spreadsheet_id,
                updated_cells=0,
            )

        try:
            # Prepare the data for batch update
            data = []
            for update in batch.updates:
                value = update.new_formula if update.new_formula else update.new_value
                data.append(
                    {
                        "range": update.range_notation,
                        "values": [[value]],
                    }
                )

            body = {
                "valueInputOption": "USER_ENTERED",
                "data": data,
            }

            result = (
                self.service.spreadsheets()
                .values()
                .batchUpdate(spreadsheetId=batch.spreadsheet_id, body=body)
                .execute()
            )

            return UpdateResult(
                success=True,
                spreadsheet_id=batch.spreadsheet_id,
                updated_cells=result.get("totalUpdatedCells", 0),
                details=[
                    {"range": r["updatedRange"], "cells": r["updatedCells"]}
                    for r in result.get("responses", [])
                ],
            )

        except HttpError as e:
            return UpdateResult(
                success=False,
                spreadsheet_id=batch.spreadsheet_id,
                errors=[str(e)],
            )

    def update_cell(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        cell: str,
        value: Optional[str] = None,
        formula: Optional[str] = None,
    ) -> UpdateResult:
        """Update a single cell."""
        batch = BatchUpdate(
            spreadsheet_id=spreadsheet_id,
            updates=[
                CellUpdate(
                    sheet_name=sheet_name,
                    cell=cell,
                    new_value=value,
                    new_formula=formula,
                )
            ],
        )
        return self.batch_update(batch)
