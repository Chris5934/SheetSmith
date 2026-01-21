"""Resolver for mapping placeholders to actual cell references."""

import logging
from typing import Optional

from ..mapping import (
    MappingManager,
)
from ..sheets import GoogleSheetsClient
from .models import (
    Placeholder,
    PlaceholderType,
    PlaceholderMapping,
    ResolvedFormula,
    ResolutionContext,
    MappingPreview,
)
from .parser import PlaceholderParser
from .syntax import fuzzy_match_score

logger = logging.getLogger(__name__)


class PlaceholderResolver:
    """Resolve placeholders to actual cell references."""

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        mapping_manager: Optional[MappingManager] = None,
    ):
        """
        Initialize the resolver.

        Args:
            sheets_client: Google Sheets client for reading data
            mapping_manager: Optional MappingManager (created if not provided)
        """
        self.sheets_client = sheets_client
        self.mapping_manager = mapping_manager or MappingManager(sheets_client)
        self.parser = PlaceholderParser()
        self._initialized = False

    async def initialize(self):
        """Initialize the resolver (creates database tables if needed)."""
        if not self._initialized:
            await self.mapping_manager.initialize()
            self._initialized = True
            logger.info("PlaceholderResolver initialized")

    async def close(self):
        """Close the resolver and cleanup resources."""
        await self.mapping_manager.close()
        self._initialized = False

    async def resolve(
        self,
        placeholder: Placeholder,
        spreadsheet_id: str,
        context: ResolutionContext,
    ) -> PlaceholderMapping:
        """
        Resolve a single placeholder to a cell reference.

        Args:
            placeholder: The placeholder to resolve
            spreadsheet_id: The spreadsheet ID
            context: Resolution context with current sheet/row info

        Returns:
            PlaceholderMapping with resolved cell reference

        Raises:
            HeaderNotFoundError: If header not found
            DisambiguationRequiredError: If multiple headers match
        """
        if placeholder.type == PlaceholderType.HEADER:
            return await self._resolve_header_placeholder(placeholder, spreadsheet_id, context)

        elif placeholder.type == PlaceholderType.INTERSECTION:
            return await self._resolve_intersection_placeholder(
                placeholder, spreadsheet_id, context
            )

        elif placeholder.type == PlaceholderType.CROSS_SHEET:
            return await self._resolve_cross_sheet_placeholder(placeholder, spreadsheet_id, context)

        elif placeholder.type == PlaceholderType.VARIABLE:
            return await self._resolve_variable_placeholder(placeholder, spreadsheet_id, context)

        else:
            raise ValueError(f"Unknown placeholder type: {placeholder.type}")

    async def _resolve_header_placeholder(
        self,
        placeholder: Placeholder,
        spreadsheet_id: str,
        context: ResolutionContext,
    ) -> PlaceholderMapping:
        """Resolve a header-based placeholder ({{header_name}})."""
        # Get column mapping for this header
        column_mapping = await self.mapping_manager.get_column_by_header(
            spreadsheet_id=spreadsheet_id,
            sheet_name=context.current_sheet,
            header_text=placeholder.name,
            auto_create=True,
        )

        # Build cell reference
        if context.absolute_references:
            cell_ref = f"${column_mapping.column_letter}${context.current_row}"
        else:
            cell_ref = f"{column_mapping.column_letter}{context.current_row}"

        return PlaceholderMapping(
            placeholder=placeholder.syntax,
            resolved_to=cell_ref,
            header=column_mapping.header_text,
            column=column_mapping.column_letter,
            row=context.current_row,
            confidence=1.0,
        )

    async def _resolve_intersection_placeholder(
        self,
        placeholder: Placeholder,
        spreadsheet_id: str,
        context: ResolutionContext,
    ) -> PlaceholderMapping:
        """Resolve an intersection placeholder ({{header:row_label}})."""
        # Get cell mapping for this intersection
        cell_mapping = await self.mapping_manager.get_concept_cell(
            spreadsheet_id=spreadsheet_id,
            sheet_name=context.current_sheet,
            column_header=placeholder.name,
            row_label=placeholder.row_label,
            auto_create=True,
        )

        # Build cell reference (always absolute for intersection)
        cell_ref = f"${cell_mapping.column_letter}${cell_mapping.row_index + 1}"

        return PlaceholderMapping(
            placeholder=placeholder.syntax,
            resolved_to=cell_ref,
            header=cell_mapping.column_header,
            column=cell_mapping.column_letter,
            row=cell_mapping.row_index + 1,
            confidence=1.0,
        )

    async def _resolve_cross_sheet_placeholder(
        self,
        placeholder: Placeholder,
        spreadsheet_id: str,
        context: ResolutionContext,
    ) -> PlaceholderMapping:
        """Resolve a cross-sheet placeholder ('Sheet'!{{header}})."""
        # Get column mapping in the target sheet
        column_mapping = await self.mapping_manager.get_column_by_header(
            spreadsheet_id=spreadsheet_id,
            sheet_name=placeholder.sheet,
            header_text=placeholder.name,
            auto_create=True,
        )

        # For cross-sheet references, we typically want absolute references
        # and often reference the first data row (row 2, assuming row 1 is header)
        row = 2  # Default to first data row
        cell_ref = f"'{placeholder.sheet}'!${column_mapping.column_letter}${row}"

        return PlaceholderMapping(
            placeholder=placeholder.syntax,
            resolved_to=cell_ref,
            header=column_mapping.header_text,
            column=column_mapping.column_letter,
            row=row,
            confidence=1.0,
            sheet_name=placeholder.sheet,
        )

    async def _resolve_variable_placeholder(
        self,
        placeholder: Placeholder,
        spreadsheet_id: str,
        context: ResolutionContext,
    ) -> PlaceholderMapping:
        """Resolve a variable placeholder (${variable})."""
        # Variables are not yet implemented - would need a variable storage system
        # For now, raise an error
        raise NotImplementedError(
            f"Variable placeholders (${{{placeholder.name}}}) are not yet implemented. "
            "Use header placeholders instead."
        )

    async def resolve_all(
        self,
        formula: str,
        spreadsheet_id: str,
        context: ResolutionContext,
    ) -> ResolvedFormula:
        """
        Resolve all placeholders in a formula.

        Args:
            formula: The formula with placeholders
            spreadsheet_id: The spreadsheet ID
            context: Resolution context

        Returns:
            ResolvedFormula with all placeholders resolved

        Raises:
            HeaderNotFoundError: If any header not found
            DisambiguationRequiredError: If any header is ambiguous
        """
        # Parse placeholders
        placeholders = self.parser.extract_placeholders(formula)

        if not placeholders:
            # No placeholders, return formula as-is
            return ResolvedFormula(
                original=formula,
                resolved=formula,
                mappings=[],
                warnings=["No placeholders found in formula"],
            )

        # Resolve each placeholder
        mappings = []
        warnings = []

        for placeholder in placeholders:
            try:
                mapping = await self.resolve(placeholder, spreadsheet_id, context)
                mappings.append(mapping)
            except NotImplementedError as e:
                warnings.append(str(e))
            except Exception as e:
                logger.error(f"Error resolving placeholder {placeholder.syntax}: {e}")
                raise

        # Build resolved formula by replacing placeholders
        resolved = formula
        # Replace in reverse order to preserve positions
        for placeholder in reversed(placeholders):
            # Find the mapping for this placeholder
            mapping = next(
                (m for m in mappings if m.placeholder == placeholder.syntax),
                None,
            )
            if mapping:
                resolved = (
                    resolved[: placeholder.start_pos]
                    + mapping.resolved_to
                    + resolved[placeholder.end_pos :]
                )

        return ResolvedFormula(
            original=formula,
            resolved=resolved,
            mappings=mappings,
            warnings=warnings,
        )

    async def preview_mappings(
        self,
        formula: str,
        spreadsheet_id: str,
        sheet_name: str,
    ) -> MappingPreview:
        """
        Preview placeholder mappings without resolving.

        Args:
            formula: The formula with placeholders
            spreadsheet_id: The spreadsheet ID
            sheet_name: The sheet name

        Returns:
            MappingPreview showing detected placeholders and potential matches
        """
        # Parse placeholders
        placeholders = self.parser.extract_placeholders(formula)

        # Get potential matches for each placeholder
        potential_mappings = {}
        requires_disambiguation = []

        for placeholder in placeholders:
            if placeholder.type in (PlaceholderType.HEADER, PlaceholderType.CROSS_SHEET):
                # Get all headers in the sheet to find potential matches
                target_sheet = placeholder.sheet if placeholder.sheet else sheet_name

                try:
                    # Read first few rows to get headers
                    sheet_range = self.sheets_client.read_range(
                        spreadsheet_id, f"{target_sheet}!1:10"
                    )

                    # Extract unique values from first row (headers)
                    headers = set()
                    for cell in sheet_range.cells:
                        if cell.row == 1 and cell.value:
                            headers.add(str(cell.value))

                    # Find fuzzy matches
                    matches = []
                    for header in headers:
                        score = fuzzy_match_score(placeholder.name, header)
                        if score > 0.5:  # Threshold for potential match
                            matches.append(header)

                    potential_mappings[placeholder.syntax] = sorted(
                        matches,
                        key=lambda h: fuzzy_match_score(placeholder.name, h),
                        reverse=True,
                    )

                    # Check if disambiguation needed
                    if len(matches) > 1:
                        requires_disambiguation.append(placeholder.syntax)

                except Exception as e:
                    logger.warning(f"Error finding matches for {placeholder.syntax}: {e}")
                    potential_mappings[placeholder.syntax] = []

        return MappingPreview(
            formula=formula,
            placeholders=placeholders,
            potential_mappings=potential_mappings,
            requires_disambiguation=requires_disambiguation,
        )
