"""Main mapping manager for header-based column and cell mappings."""

import logging
from datetime import datetime, timezone
from typing import Optional

from ..sheets import GoogleSheetsClient
from .models import (
    ColumnMapping,
    CellMapping,
    DisambiguationResponse,
    DisambiguationRequiredError,
    MappingNotFoundError,
    HeaderNotFoundError,
    MappingStatus,
    MappingAuditEntry,
    MappingAuditReport,
)
from .storage import MappingStorage
from .validator import MappingValidator
from .disambiguator import DisambiguationHandler

logger = logging.getLogger(__name__)


class MappingManager:
    """
    Manages header-based column and cell mappings.

    This is the main entry point for all mapping operations. It coordinates
    between storage, validation, and disambiguation.
    """

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        storage: Optional[MappingStorage] = None,
    ):
        """
        Initialize the mapping manager.

        Args:
            sheets_client: Google Sheets client for reading spreadsheet data
            storage: Optional MappingStorage instance (created if not provided)
        """
        self.sheets_client = sheets_client
        self.storage = storage or MappingStorage()
        self.validator = MappingValidator(sheets_client)
        self.disambiguator = DisambiguationHandler()
        self._initialized = False

    async def initialize(self):
        """Initialize the mapping manager (creates database tables if needed)."""
        if not self._initialized:
            await self.storage.initialize()
            self._initialized = True
            logger.info("MappingManager initialized")

    async def close(self):
        """Close the mapping manager and cleanup resources."""
        await self.storage.close()
        self._initialized = False

    async def get_column_by_header(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        header_text: str,
        auto_create: bool = True,
    ) -> ColumnMapping:
        """
        Get a column mapping by header text.

        This will:
        1. Check if a cached mapping exists
        2. If exists, validate it's still accurate
        3. If not exists or invalid, search for the header
        4. If multiple headers found, raise DisambiguationRequiredError
        5. If single header found, create/update mapping
        6. If no header found, raise HeaderNotFoundError

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: The sheet name
            header_text: The header text to search for
            auto_create: Automatically create mapping if not cached (default True)

        Returns:
            ColumnMapping for the header

        Raises:
            DisambiguationRequiredError: If multiple columns have the same header
            HeaderNotFoundError: If header not found in sheet
            MappingNotFoundError: If mapping not found and auto_create is False
        """
        # Check if we have a cached mapping
        cached = await self.storage.get_column_mapping(spreadsheet_id, sheet_name, header_text)

        if cached:
            # Validate the cached mapping
            validation = await self.validator.validate_column_mapping(cached)

            if validation.status == MappingStatus.VALID:
                # Mapping is still valid, update last_validated_at
                cached.last_validated_at = datetime.now(timezone.utc)
                await self.storage.store_column_mapping(cached)
                return cached

            elif validation.status == MappingStatus.MOVED:
                # Header moved, update the mapping
                logger.info(
                    f"Header '{header_text}' moved from {validation.old_column_letter} "
                    f"to {validation.new_column_letter}"
                )
                cached.column_letter = validation.new_column_letter
                cached.column_index = self.validator._column_letter_to_index(
                    validation.new_column_letter
                )
                cached.last_validated_at = datetime.now(timezone.utc)
                await self.storage.store_column_mapping(cached)
                return cached

            elif validation.status == MappingStatus.AMBIGUOUS:
                # Multiple headers found, need disambiguation
                request = self.disambiguator.create_disambiguation_request(
                    spreadsheet_id, sheet_name, header_text, validation.candidates
                )
                raise DisambiguationRequiredError(request)

            elif validation.status == MappingStatus.MISSING:
                # Header no longer exists
                logger.warning(f"Header '{header_text}' no longer found, deleting mapping")
                if cached.id:
                    await self.storage.delete_column_mapping(cached.id)
                raise HeaderNotFoundError(
                    f"Header '{header_text}' not found in sheet '{sheet_name}'"
                )

        # No cached mapping or validation failed, search for the header
        if not auto_create:
            raise MappingNotFoundError(
                f"No mapping found for header '{header_text}' in sheet '{sheet_name}'"
            )

        # Search for the header in the sheet
        candidates = await self.validator._find_header_in_sheet(
            spreadsheet_id, sheet_name, header_text
        )

        if len(candidates) == 0:
            raise HeaderNotFoundError(f"Header '{header_text}' not found in sheet '{sheet_name}'")

        if len(candidates) > 1:
            # Multiple headers found, need disambiguation
            request = self.disambiguator.create_disambiguation_request(
                spreadsheet_id, sheet_name, header_text, candidates
            )
            raise DisambiguationRequiredError(request)

        # Single header found, create mapping
        candidate = candidates[0]
        mapping = ColumnMapping(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            header_text=header_text,
            column_letter=candidate.column_letter,
            column_index=candidate.column_index,
            header_row=candidate.header_row,
            last_validated_at=datetime.now(timezone.utc),
        )

        await self.storage.store_column_mapping(mapping)
        logger.info(
            f"Created column mapping: {sheet_name}/{header_text} -> {candidate.column_letter}"
        )

        return mapping

    async def get_concept_cell(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        column_header: str,
        row_label: str,
        auto_create: bool = True,
    ) -> CellMapping:
        """
        Get a concept cell mapping by column header × row label intersection.

        This will:
        1. Check if a cached mapping exists
        2. If exists, validate it's still accurate
        3. If not exists or invalid, search for header and row label
        4. Create/update mapping with cell address

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: The sheet name
            column_header: The column header text
            row_label: The row label text (usually in first column)
            auto_create: Automatically create mapping if not cached (default True)

        Returns:
            CellMapping for the intersection

        Raises:
            DisambiguationRequiredError: If multiple columns have the same header
            HeaderNotFoundError: If header or row label not found
            MappingNotFoundError: If mapping not found and auto_create is False
        """
        # Check if we have a cached mapping
        cached = await self.storage.get_cell_mapping(
            spreadsheet_id, sheet_name, column_header, row_label
        )

        if cached:
            # Validate the cached mapping
            validation = await self.validator.validate_cell_mapping(cached)

            if validation.status == MappingStatus.VALID:
                # Mapping is still valid
                cached.last_validated_at = datetime.now(timezone.utc)
                await self.storage.store_cell_mapping(cached)
                return cached

            elif validation.status == MappingStatus.MOVED:
                # Cell moved, update the mapping
                logger.info(
                    f"Cell '{column_header} × {row_label}' moved from "
                    f"{cached.cell_address} to {validation.new_column_letter}"
                )
                cached.cell_address = validation.new_column_letter
                # Parse the new cell address to update column and row
                col_letter = "".join(c for c in cached.cell_address if c.isalpha())
                row_num = int("".join(c for c in cached.cell_address if c.isdigit()))
                cached.column_letter = col_letter
                cached.column_index = self.validator._column_letter_to_index(col_letter)
                cached.row_index = row_num - 1
                cached.last_validated_at = datetime.now(timezone.utc)
                await self.storage.store_cell_mapping(cached)
                return cached

            elif validation.status == MappingStatus.AMBIGUOUS:
                # Multiple headers found
                request = self.disambiguator.create_disambiguation_request(
                    spreadsheet_id, sheet_name, column_header, validation.candidates
                )
                raise DisambiguationRequiredError(request)

            else:  # MISSING
                # Delete the invalid mapping
                if cached.id:
                    await self.storage.delete_cell_mapping(cached.id)
                raise HeaderNotFoundError(
                    f"Header '{column_header}' or row '{row_label}' not found"
                )

        # No cached mapping, search for header and row
        if not auto_create:
            raise MappingNotFoundError(f"No mapping found for cell '{column_header} × {row_label}'")

        # Search for the column header
        header_candidates = await self.validator._find_header_in_sheet(
            spreadsheet_id, sheet_name, column_header
        )

        if len(header_candidates) == 0:
            raise HeaderNotFoundError(
                f"Column header '{column_header}' not found in sheet '{sheet_name}'"
            )

        if len(header_candidates) > 1:
            request = self.disambiguator.create_disambiguation_request(
                spreadsheet_id, sheet_name, column_header, header_candidates
            )
            raise DisambiguationRequiredError(request)

        # Search for the row label
        row_index = await self.validator._find_row_label_in_sheet(
            spreadsheet_id, sheet_name, row_label
        )

        if row_index is None:
            raise HeaderNotFoundError(f"Row label '{row_label}' not found in sheet '{sheet_name}'")

        # Create the cell mapping
        header_candidate = header_candidates[0]
        cell_address = f"{header_candidate.column_letter}{row_index + 1}"

        mapping = CellMapping(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            column_header=column_header,
            row_label=row_label,
            cell_address=cell_address,
            row_index=row_index,
            column_letter=header_candidate.column_letter,
            column_index=header_candidate.column_index,
            last_validated_at=datetime.now(timezone.utc),
        )

        await self.storage.store_cell_mapping(mapping)
        logger.info(
            f"Created cell mapping: {sheet_name}/{column_header} × {row_label} -> "
            f"{cell_address}"
        )

        return mapping

    async def validate_mapping(self, mapping_id: int, mapping_type: str = "column") -> dict:
        """
        Validate a specific mapping by ID.

        Args:
            mapping_id: The mapping ID
            mapping_type: "column" or "cell"

        Returns:
            Dict with validation results
        """
        if mapping_type == "column":
            # Get all column mappings and find the one with this ID
            # This is inefficient but works for now
            # TODO: Add get_by_id methods to storage
            pass
        else:
            pass

        # For now, return a placeholder
        return {"status": "not_implemented"}

    async def store_disambiguation(self, response: DisambiguationResponse) -> ColumnMapping:
        """
        Store user's disambiguation choice and create mapping.

        Args:
            response: User's disambiguation response

        Returns:
            ColumnMapping created from the disambiguation

        Raises:
            ValueError: If request not found or invalid
        """
        # Get the disambiguation request
        request = self.disambiguator.get_disambiguation_request(response.request_id)
        if request is None:
            raise ValueError(f"Disambiguation request {response.request_id} not found or expired")

        # Resolve the disambiguation
        selected = self.disambiguator.resolve_disambiguation(response)

        # Create the mapping
        mapping = self.disambiguator.create_mapping_from_resolution(request, response, selected)

        # Store the mapping
        await self.storage.store_column_mapping(mapping)

        logger.info(
            f"Stored disambiguation result: {mapping.sheet_name}/{mapping.header_text} "
            f"-> {mapping.column_letter}"
        )

        return mapping

    async def audit_mappings(self, spreadsheet_id: str) -> MappingAuditReport:
        """
        Audit all mappings for a spreadsheet.

        This checks the health of all cached mappings and returns a report
        showing which are valid, moved, missing, or ambiguous.

        Args:
            spreadsheet_id: The spreadsheet ID to audit

        Returns:
            MappingAuditReport with status of all mappings
        """
        # Get spreadsheet info
        try:
            info = self.sheets_client.get_spreadsheet_info(spreadsheet_id)
            spreadsheet_title = info.get("title", "Unknown")
        except Exception:
            spreadsheet_title = None

        # Get all column mappings
        column_mappings = await self.storage.get_all_column_mappings(spreadsheet_id)

        # Get all cell mappings
        cell_mappings = await self.storage.get_all_cell_mappings(spreadsheet_id)

        entries = []
        valid_count = 0
        moved_count = 0
        missing_count = 0
        ambiguous_count = 0

        # Validate each column mapping
        for mapping in column_mappings:
            validation = await self.validator.validate_column_mapping(mapping)

            if validation.status == MappingStatus.VALID:
                valid_count += 1
            elif validation.status == MappingStatus.MOVED:
                moved_count += 1
            elif validation.status == MappingStatus.MISSING:
                missing_count += 1
            elif validation.status == MappingStatus.AMBIGUOUS:
                ambiguous_count += 1

            entries.append(
                MappingAuditEntry(
                    mapping_id=mapping.id,
                    mapping_type="column",
                    spreadsheet_id=mapping.spreadsheet_id,
                    sheet_name=mapping.sheet_name,
                    header_text=mapping.header_text,
                    current_address=mapping.column_letter,
                    status=validation.status,
                    last_validated_at=mapping.last_validated_at,
                    created_at=mapping.created_at,
                    needs_action=validation.status != MappingStatus.VALID,
                )
            )

        # Validate each cell mapping
        for mapping in cell_mappings:
            validation = await self.validator.validate_cell_mapping(mapping)

            if validation.status == MappingStatus.VALID:
                valid_count += 1
            elif validation.status == MappingStatus.MOVED:
                moved_count += 1
            elif validation.status == MappingStatus.MISSING:
                missing_count += 1
            elif validation.status == MappingStatus.AMBIGUOUS:
                ambiguous_count += 1

            entries.append(
                MappingAuditEntry(
                    mapping_id=mapping.id,
                    mapping_type="cell",
                    spreadsheet_id=mapping.spreadsheet_id,
                    sheet_name=mapping.sheet_name,
                    header_text=mapping.column_header,
                    row_label=mapping.row_label,
                    current_address=mapping.cell_address,
                    status=validation.status,
                    last_validated_at=mapping.last_validated_at,
                    created_at=mapping.created_at,
                    needs_action=validation.status != MappingStatus.VALID,
                )
            )

        report = MappingAuditReport(
            spreadsheet_id=spreadsheet_id,
            spreadsheet_title=spreadsheet_title,
            total_mappings=len(entries),
            valid_count=valid_count,
            moved_count=moved_count,
            missing_count=missing_count,
            ambiguous_count=ambiguous_count,
            entries=entries,
        )

        logger.info(
            f"Audit complete for {spreadsheet_id}: {valid_count} valid, "
            f"{moved_count} moved, {missing_count} missing, {ambiguous_count} ambiguous"
        )

        return report

    async def delete_mapping(self, mapping_id: int, mapping_type: str = "column") -> bool:
        """
        Delete a mapping by ID.

        Args:
            mapping_id: The mapping ID
            mapping_type: "column" or "cell"

        Returns:
            True if deleted, False if not found
        """
        if mapping_type == "column":
            return await self.storage.delete_column_mapping(mapping_id)
        else:
            return await self.storage.delete_cell_mapping(mapping_id)
