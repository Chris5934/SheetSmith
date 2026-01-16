"""SQLite-based memory store for persistence."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from ..config import settings
from .models import Rule, LogicBlock, AuditLog, FixSummary


class MemoryStore:
    """Persistent storage for rules, logic blocks, and audit logs."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.database_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize the database and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))

        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                rule_type TEXT NOT NULL,
                content TEXT NOT NULL,
                examples TEXT,
                created_at TEXT,
                updated_at TEXT,
                tags TEXT
            );

            CREATE TABLE IF NOT EXISTS logic_blocks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                block_type TEXT NOT NULL,
                description TEXT,
                formula_pattern TEXT NOT NULL,
                variables TEXT,
                version TEXT,
                created_at TEXT,
                updated_at TEXT,
                tags TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                spreadsheet_id TEXT,
                description TEXT,
                details TEXT,
                user_approved INTEGER,
                changes_applied INTEGER
            );

            CREATE TABLE IF NOT EXISTS fix_summaries (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                spreadsheet_id TEXT NOT NULL,
                timestamp TEXT,
                pattern_searched TEXT,
                cells_modified INTEGER,
                before_example TEXT,
                after_example TEXT,
                tags TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_rules_type ON rules(rule_type);
            CREATE INDEX IF NOT EXISTS idx_logic_blocks_type ON logic_blocks(block_type);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_fix_summaries_spreadsheet ON fix_summaries(spreadsheet_id);
            """
        )
        await self._connection.commit()

    async def close(self):
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # Rule operations
    async def store_rule(self, rule: Rule) -> Rule:
        """Store or update a rule."""
        if not rule.id:
            rule.id = str(uuid.uuid4())
        rule.updated_at = datetime.utcnow()

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO rules
            (id, name, description, rule_type, content, examples, created_at, updated_at, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.id,
                rule.name,
                rule.description,
                rule.rule_type,
                rule.content,
                json.dumps(rule.examples),
                rule.created_at.isoformat(),
                rule.updated_at.isoformat(),
                json.dumps(rule.tags),
            ),
        )
        await self._connection.commit()
        return rule

    async def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        async with self._connection.execute(
            "SELECT * FROM rules WHERE id = ?", (rule_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_rule(row)
        return None

    async def get_rules(
        self, rule_type: Optional[str] = None, tags: Optional[list[str]] = None
    ) -> list[Rule]:
        """Get all rules, optionally filtered by type or tags."""
        query = "SELECT * FROM rules"
        params = []

        if rule_type:
            query += " WHERE rule_type = ?"
            params.append(rule_type)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            rules = [self._row_to_rule(row) for row in rows]

            if tags:
                rules = [r for r in rules if any(t in r.tags for t in tags)]

            return rules

    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by ID."""
        cursor = await self._connection.execute(
            "DELETE FROM rules WHERE id = ?", (rule_id,)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    def _row_to_rule(self, row) -> Rule:
        return Rule(
            id=row[0],
            name=row[1],
            description=row[2],
            rule_type=row[3],
            content=row[4],
            examples=json.loads(row[5]) if row[5] else [],
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row[7]) if row[7] else datetime.utcnow(),
            tags=json.loads(row[8]) if row[8] else [],
        )

    # Logic block operations
    async def store_logic_block(self, block: LogicBlock) -> LogicBlock:
        """Store or update a logic block."""
        if not block.id:
            block.id = str(uuid.uuid4())
        block.updated_at = datetime.utcnow()

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO logic_blocks
            (id, name, block_type, description, formula_pattern, variables, version, created_at, updated_at, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block.id,
                block.name,
                block.block_type,
                block.description,
                block.formula_pattern,
                json.dumps(block.variables),
                block.version,
                block.created_at.isoformat(),
                block.updated_at.isoformat(),
                json.dumps(block.tags),
            ),
        )
        await self._connection.commit()
        return block

    async def get_logic_block(self, block_id: str) -> Optional[LogicBlock]:
        """Get a logic block by ID."""
        async with self._connection.execute(
            "SELECT * FROM logic_blocks WHERE id = ?", (block_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_logic_block(row)
        return None

    async def get_logic_blocks(
        self, block_type: Optional[str] = None, tags: Optional[list[str]] = None
    ) -> list[LogicBlock]:
        """Get all logic blocks, optionally filtered."""
        query = "SELECT * FROM logic_blocks"
        params = []

        if block_type:
            query += " WHERE block_type = ?"
            params.append(block_type)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            blocks = [self._row_to_logic_block(row) for row in rows]

            if tags:
                blocks = [b for b in blocks if any(t in b.tags for t in tags)]

            return blocks

    async def search_logic_blocks(self, query: str) -> list[LogicBlock]:
        """Search logic blocks by name or description."""
        async with self._connection.execute(
            """
            SELECT * FROM logic_blocks
            WHERE name LIKE ? OR description LIKE ? OR formula_pattern LIKE ?
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_logic_block(row) for row in rows]

    def _row_to_logic_block(self, row) -> LogicBlock:
        return LogicBlock(
            id=row[0],
            name=row[1],
            block_type=row[2],
            description=row[3],
            formula_pattern=row[4],
            variables=json.loads(row[5]) if row[5] else {},
            version=row[6] or "1.0",
            created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row[8]) if row[8] else datetime.utcnow(),
            tags=json.loads(row[9]) if row[9] else [],
        )

    # Audit log operations
    async def log_action(self, log: AuditLog) -> AuditLog:
        """Record an audit log entry."""
        if not log.id:
            log.id = str(uuid.uuid4())

        await self._connection.execute(
            """
            INSERT INTO audit_logs
            (id, timestamp, action, spreadsheet_id, description, details, user_approved, changes_applied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log.id,
                log.timestamp.isoformat(),
                log.action,
                log.spreadsheet_id,
                log.description,
                json.dumps(log.details),
                1 if log.user_approved else 0,
                log.changes_applied,
            ),
        )
        await self._connection.commit()
        return log

    async def get_audit_logs(
        self,
        spreadsheet_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get audit logs, optionally filtered."""
        query = "SELECT * FROM audit_logs"
        conditions = []
        params = []

        if spreadsheet_id:
            conditions.append("spreadsheet_id = ?")
            params.append(spreadsheet_id)
        if action:
            conditions.append("action = ?")
            params.append(action)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_audit_log(row) for row in rows]

    def _row_to_audit_log(self, row) -> AuditLog:
        return AuditLog(
            id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            action=row[2],
            spreadsheet_id=row[3],
            description=row[4],
            details=json.loads(row[5]) if row[5] else {},
            user_approved=bool(row[6]),
            changes_applied=row[7] or 0,
        )

    # Fix summary operations
    async def store_fix_summary(self, summary: FixSummary) -> FixSummary:
        """Store a fix summary."""
        if not summary.id:
            summary.id = str(uuid.uuid4())

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO fix_summaries
            (id, title, description, spreadsheet_id, timestamp, pattern_searched,
             cells_modified, before_example, after_example, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.id,
                summary.title,
                summary.description,
                summary.spreadsheet_id,
                summary.timestamp.isoformat(),
                summary.pattern_searched,
                summary.cells_modified,
                summary.before_example,
                summary.after_example,
                json.dumps(summary.tags),
            ),
        )
        await self._connection.commit()
        return summary

    async def get_fix_summaries(
        self, spreadsheet_id: Optional[str] = None, limit: int = 50
    ) -> list[FixSummary]:
        """Get fix summaries."""
        if spreadsheet_id:
            query = "SELECT * FROM fix_summaries WHERE spreadsheet_id = ? ORDER BY timestamp DESC LIMIT ?"
            params = (spreadsheet_id, limit)
        else:
            query = "SELECT * FROM fix_summaries ORDER BY timestamp DESC LIMIT ?"
            params = (limit,)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_fix_summary(row) for row in rows]

    def _row_to_fix_summary(self, row) -> FixSummary:
        return FixSummary(
            id=row[0],
            title=row[1],
            description=row[2],
            spreadsheet_id=row[3],
            timestamp=datetime.fromisoformat(row[4]) if row[4] else datetime.utcnow(),
            pattern_searched=row[5],
            cells_modified=row[6] or 0,
            before_example=row[7],
            after_example=row[8],
            tags=json.loads(row[9]) if row[9] else [],
        )
