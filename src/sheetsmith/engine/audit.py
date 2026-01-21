"""Audit logger for operations."""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """Single audit log entry (enhanced model per spec)."""
    id: str
    timestamp: str
    operation_type: str
    spreadsheet_id: str
    user: str
    preview_id: Optional[str]
    scope: dict  # Serialized OperationScope
    status: str  # "success", "failed", "cancelled"
    changes_applied: int
    errors: list[str]
    duration_ms: float


class AuditLogger:
    """
    Logs all operations for audit trail.
    
    This is a wrapper around the MemoryStore audit functionality
    to provide the interface specified in the requirements.
    """
    
    def __init__(self, memory_store=None):
        """
        Initialize audit logger.
        
        Args:
            memory_store: MemoryStore instance for persistence
        """
        self.memory_store = memory_store
        logger.info("AuditLogger initialized")
    
    async def initialize(self):
        """Initialize audit log storage."""
        if self.memory_store:
            await self.memory_store.initialize()
        logger.info("AuditLogger initialized successfully")
    
    async def log_operation(self, entry: AuditEntry):
        """
        Log an operation to the audit trail.
        
        Args:
            entry: AuditEntry to log
        """
        if not self.memory_store:
            logger.warning("No memory store configured, skipping audit log")
            return
        
        # Convert to MemoryStore AuditLog format
        from ..memory.models import AuditLog
        
        audit_log = AuditLog(
            id=entry.id,
            timestamp=datetime.fromisoformat(entry.timestamp) if isinstance(entry.timestamp, str) else entry.timestamp,
            action=entry.operation_type,
            spreadsheet_id=entry.spreadsheet_id,
            description=f"{entry.operation_type} - {entry.status}",
            details={
                "preview_id": entry.preview_id,
                "scope": entry.scope,
                "user": entry.user,
                "errors": entry.errors,
                "duration_ms": entry.duration_ms,
            },
            user_approved=entry.status == "success",
            changes_applied=entry.changes_applied,
        )
        
        await self.memory_store.log_audit(audit_log)
        logger.info(
            f"Logged audit entry: {entry.id} - {entry.operation_type} - "
            f"{entry.status} - {entry.changes_applied} changes"
        )
    
    async def get_recent_operations(
        self,
        limit: int = 50,
        spreadsheet_id: Optional[str] = None
    ) -> list[AuditEntry]:
        """
        Retrieve recent operations from audit log.
        
        Args:
            limit: Maximum number of entries to return
            spreadsheet_id: Filter by spreadsheet ID (optional)
            
        Returns:
            List of AuditEntry objects
        """
        if not self.memory_store:
            logger.warning("No memory store configured, returning empty list")
            return []
        
        # Get logs from memory store
        logs = await self.memory_store.get_audit_logs(
            spreadsheet_id=spreadsheet_id,
            limit=limit
        )
        
        # Convert to AuditEntry format
        entries = []
        for log in logs:
            # Extract details from the stored log
            details = log.details or {}
            
            entry = AuditEntry(
                id=log.id,
                timestamp=log.timestamp.isoformat(),
                operation_type=log.action,
                spreadsheet_id=log.spreadsheet_id or "",
                user=details.get("user", "unknown"),
                preview_id=details.get("preview_id"),
                scope=details.get("scope", {}),
                status="success" if log.user_approved else "failed",
                changes_applied=log.changes_applied,
                errors=details.get("errors", []),
                duration_ms=details.get("duration_ms", 0.0),
            )
            entries.append(entry)
        
        return entries
