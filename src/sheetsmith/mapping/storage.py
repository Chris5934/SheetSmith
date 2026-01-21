"""Database persistence layer for header-based mappings."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from ..config import settings
from .models import ColumnMapping, CellMapping

logger = logging.getLogger(__name__)


class MappingStorage:
    """Manages database storage for column and cell mappings."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.database_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize the database and create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))

        # Create column_mappings table
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS column_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spreadsheet_id TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                header_text TEXT NOT NULL,
                row_label TEXT NULL,
                column_letter TEXT NOT NULL,
                column_index INTEGER NOT NULL,
                header_row INTEGER NOT NULL DEFAULT 0,
                cell_address TEXT NULL,
                disambiguation_context TEXT NULL,
                last_validated_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(spreadsheet_id, sheet_name, header_text, row_label)
            );
            
            CREATE INDEX IF NOT EXISTS idx_column_mappings_spreadsheet 
                ON column_mappings(spreadsheet_id, sheet_name);
            CREATE INDEX IF NOT EXISTS idx_column_mappings_header 
                ON column_mappings(spreadsheet_id, sheet_name, header_text);
            """
        )
        await self._connection.commit()
        logger.info("MappingStorage initialized")

    async def close(self):
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # Column mapping operations

    async def store_column_mapping(self, mapping: ColumnMapping) -> ColumnMapping:
        """Store or update a column mapping."""
        if not mapping.created_at:
            mapping.created_at = datetime.utcnow()

        disambiguation_json = (
            json.dumps(mapping.disambiguation_context)
            if mapping.disambiguation_context
            else None
        )

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO column_mappings
            (spreadsheet_id, sheet_name, header_text, row_label, column_letter, 
             column_index, header_row, cell_address, disambiguation_context, 
             last_validated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping.spreadsheet_id,
                mapping.sheet_name,
                mapping.header_text,
                None,  # row_label is NULL for column mappings
                mapping.column_letter,
                mapping.column_index,
                mapping.header_row,
                None,  # cell_address is NULL for column mappings
                disambiguation_json,
                (
                    mapping.last_validated_at.isoformat()
                    if mapping.last_validated_at
                    else None
                ),
                mapping.created_at.isoformat(),
            ),
        )
        await self._connection.commit()

        # Get the ID if it's a new mapping
        if mapping.id is None:
            cursor = await self._connection.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            mapping.id = row[0]

        logger.info(
            f"Stored column mapping: {mapping.spreadsheet_id}/{mapping.sheet_name}/"
            f"{mapping.header_text} -> {mapping.column_letter}"
        )
        return mapping

    async def get_column_mapping(
        self, spreadsheet_id: str, sheet_name: str, header_text: str
    ) -> Optional[ColumnMapping]:
        """Get a column mapping by spreadsheet, sheet, and header text."""
        async with self._connection.execute(
            """
            SELECT id, spreadsheet_id, sheet_name, header_text, column_letter, 
                   column_index, header_row, disambiguation_context, 
                   last_validated_at, created_at
            FROM column_mappings
            WHERE spreadsheet_id = ? AND sheet_name = ? AND header_text = ? 
                  AND row_label IS NULL
            """,
            (spreadsheet_id, sheet_name, header_text),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_column_mapping(row)
        return None

    async def get_all_column_mappings(
        self, spreadsheet_id: str, sheet_name: Optional[str] = None
    ) -> list[ColumnMapping]:
        """Get all column mappings for a spreadsheet, optionally filtered by sheet."""
        query = """
            SELECT id, spreadsheet_id, sheet_name, header_text, column_letter, 
                   column_index, header_row, disambiguation_context, 
                   last_validated_at, created_at
            FROM column_mappings
            WHERE spreadsheet_id = ? AND row_label IS NULL
        """
        params = [spreadsheet_id]

        if sheet_name:
            query += " AND sheet_name = ?"
            params.append(sheet_name)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_column_mapping(row) for row in rows]

    async def delete_column_mapping(self, mapping_id: int) -> bool:
        """Delete a column mapping by ID."""
        cursor = await self._connection.execute(
            "DELETE FROM column_mappings WHERE id = ? AND row_label IS NULL", (mapping_id,)
        )
        await self._connection.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted column mapping ID {mapping_id}")
        return deleted

    def _row_to_column_mapping(self, row) -> ColumnMapping:
        """Convert a database row to a ColumnMapping object."""
        return ColumnMapping(
            id=row[0],
            spreadsheet_id=row[1],
            sheet_name=row[2],
            header_text=row[3],
            column_letter=row[4],
            column_index=row[5],
            header_row=row[6],
            disambiguation_context=json.loads(row[7]) if row[7] else None,
            last_validated_at=(datetime.fromisoformat(row[8]) if row[8] else None),
            created_at=datetime.fromisoformat(row[9]),
        )

    # Cell mapping operations

    async def store_cell_mapping(self, mapping: CellMapping) -> CellMapping:
        """Store or update a cell mapping."""
        if not mapping.created_at:
            mapping.created_at = datetime.utcnow()

        disambiguation_json = (
            json.dumps(mapping.disambiguation_context)
            if mapping.disambiguation_context
            else None
        )

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO column_mappings
            (spreadsheet_id, sheet_name, header_text, row_label, column_letter, 
             column_index, header_row, cell_address, disambiguation_context, 
             last_validated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping.spreadsheet_id,
                mapping.sheet_name,
                mapping.column_header,
                mapping.row_label,
                mapping.column_letter,
                mapping.column_index,
                mapping.row_index,  # Store row_index in header_row column
                mapping.cell_address,
                disambiguation_json,
                (
                    mapping.last_validated_at.isoformat()
                    if mapping.last_validated_at
                    else None
                ),
                mapping.created_at.isoformat(),
            ),
        )
        await self._connection.commit()

        # Get the ID if it's a new mapping
        if mapping.id is None:
            cursor = await self._connection.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            mapping.id = row[0]

        logger.info(
            f"Stored cell mapping: {mapping.spreadsheet_id}/{mapping.sheet_name}/"
            f"{mapping.column_header} × {mapping.row_label} -> {mapping.cell_address}"
        )
        return mapping

    async def get_cell_mapping(
        self, spreadsheet_id: str, sheet_name: str, column_header: str, row_label: str
    ) -> Optional[CellMapping]:
        """Get a cell mapping by spreadsheet, sheet, column header, and row label."""
        async with self._connection.execute(
            """
            SELECT id, spreadsheet_id, sheet_name, header_text, row_label, 
                   column_letter, column_index, header_row, cell_address, 
                   disambiguation_context, last_validated_at, created_at
            FROM column_mappings
            WHERE spreadsheet_id = ? AND sheet_name = ? 
                  AND header_text = ? AND row_label = ?
            """,
            (spreadsheet_id, sheet_name, column_header, row_label),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_cell_mapping(row)
        return None

    async def get_all_cell_mappings(
        self, spreadsheet_id: str, sheet_name: Optional[str] = None
    ) -> list[CellMapping]:
        """Get all cell mappings for a spreadsheet, optionally filtered by sheet."""
        query = """
            SELECT id, spreadsheet_id, sheet_name, header_text, row_label, 
                   column_letter, column_index, header_row, cell_address, 
                   disambiguation_context, last_validated_at, created_at
            FROM column_mappings
            WHERE spreadsheet_id = ? AND row_label IS NOT NULL
        """
        params = [spreadsheet_id]

        if sheet_name:
            query += " AND sheet_name = ?"
            params.append(sheet_name)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_cell_mapping(row) for row in rows]

    async def delete_cell_mapping(self, mapping_id: int) -> bool:
        """Delete a cell mapping by ID."""
        cursor = await self._connection.execute(
            "DELETE FROM column_mappings WHERE id = ? AND row_label IS NOT NULL",
            (mapping_id,),
        )
        await self._connection.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted cell mapping ID {mapping_id}")
        return deleted

    def _row_to_cell_mapping(self, row) -> CellMapping:
        """Convert a database row to a CellMapping object."""
        return CellMapping(
            id=row[0],
            spreadsheet_id=row[1],
            sheet_name=row[2],
            column_header=row[3],
            row_label=row[4],
            column_letter=row[5],
            column_index=row[6],
            row_index=row[7],  # header_row column stores row_index for cell mappings
            cell_address=row[8],
            disambiguation_context=json.loads(row[9]) if row[9] else None,
            last_validated_at=(datetime.fromisoformat(row[10]) if row[10] else None),
            created_at=datetime.fromisoformat(row[11]),
        )

    # Utility methods

    async def delete_all_mappings(
        self, spreadsheet_id: str, sheet_name: Optional[str] = None
    ) -> int:
        """Delete all mappings for a spreadsheet, optionally filtered by sheet."""
        query = "DELETE FROM column_mappings WHERE spreadsheet_id = ?"
        params = [spreadsheet_id]

        if sheet_name:
            query += " AND sheet_name = ?"
            params.append(sheet_name)

        cursor = await self._connection.execute(query, params)
        await self._connection.commit()
        count = cursor.rowcount
        logger.info(
            f"Deleted {count} mappings for {spreadsheet_id}"
            + (f"/{sheet_name}" if sheet_name else "")
        )
        return count
