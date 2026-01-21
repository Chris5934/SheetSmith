"""Main deterministic operations engine."""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from ..sheets import GoogleSheetsClient
from ..memory import MemoryStore
from ..engine.safety import SafetyValidator, OperationScope
from ..engine.scope import ScopeAnalyzer
from ..engine.audit import AuditLogger
from .models import (
    SearchCriteria,
    SearchResult,
    Operation,
    PreviewResponse,
    ApplyResponse,
)
from .search import CellSearchEngine
from .preview import PreviewGenerator
from .apply import ApplyEngine
from .cache import PreviewCache

logger = logging.getLogger(__name__)


class SafetyCheckFailedError(Exception):
    """Raised when safety checks fail for an operation."""
    pass


class DeterministicOpsEngine:
    """
    Engine for deterministic spreadsheet operations.
    
    This engine handles spreadsheet manipulations without LLM involvement.
    All operations are deterministic and based on explicit criteria.
    """

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        memory_store: Optional[MemoryStore] = None,
    ):
        """
        Initialize the ops engine.
        
        Args:
            sheets_client: Google Sheets client (created if not provided)
            memory_store: Memory store for audit logging (optional)
        """
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.memory_store = memory_store
        
        # Initialize sub-engines
        self.search_engine = CellSearchEngine(self.sheets_client)
        self.preview_generator = PreviewGenerator(
            self.sheets_client, self.search_engine
        )
        self.apply_engine = ApplyEngine(self.sheets_client, self.memory_store)
        
        # Safety components
        self.safety_validator = SafetyValidator()
        self.scope_analyzer = ScopeAnalyzer(self.sheets_client)
        self.audit_logger = AuditLogger(self.memory_store)
        
        # Preview cache
        self.preview_cache = PreviewCache(default_ttl_minutes=30)
        
        logger.info("DeterministicOpsEngine initialized with safety features")

    def search(
        self, spreadsheet_id: str, criteria: SearchCriteria, limit: int = 1000
    ) -> SearchResult:
        """
        Search for cells matching criteria.
        
        This is a deterministic operation that:
        - Searches by header name (never by column letter)
        - Supports row label filtering
        - Matches formula patterns (exact or regex)
        - Matches value patterns
        - Returns all matches with location metadata
        
        Args:
            spreadsheet_id: The spreadsheet to search
            criteria: Search criteria
            limit: Maximum number of matches to return
            
        Returns:
            SearchResult with matching cells
        """
        logger.info(f"Executing search on {spreadsheet_id}")
        
        result = self.search_engine.search(spreadsheet_id, criteria, limit)
        
        logger.info(
            f"Search completed: {result.total_count} matches in "
            f"{len(result.searched_sheets)} sheets "
            f"({result.execution_time_ms:.2f}ms)"
        )
        
        return result

    def generate_preview(
        self, spreadsheet_id: str, operation: Operation, ttl_minutes: int = 30, dry_run: bool = False
    ) -> PreviewResponse:
        """
        Generate a preview of proposed changes.
        
        This shows:
        - Before/after values for each affected cell
        - Clear scope summary (number of sheets, cells, headers affected)
        - Location info for every change
        
        Args:
            spreadsheet_id: The spreadsheet to operate on
            operation: The operation to preview
            ttl_minutes: Time to live for the preview (default 30 minutes)
            dry_run: If True, only validate and preview without storing for apply
            
        Returns:
            PreviewResponse with changes and metadata
        """
        logger.info(
            f"Generating preview for {operation.operation_type} on {spreadsheet_id} "
            f"(dry_run={dry_run})"
        )
        
        preview = self.preview_generator.generate_preview(
            spreadsheet_id, operation, ttl_minutes, dry_run
        )
        
        # Store in cache only if not dry-run
        if not dry_run:
            self.preview_cache.store(preview, ttl_minutes)
        
        logger.info(
            f"Preview generated: {preview.preview_id} - "
            f"{preview.scope.total_cells} cells affected in "
            f"{preview.scope.sheet_count} sheets"
        )
        
        return preview

    async def apply_changes(
        self, preview_id: str, confirmation: bool = False, dry_run: bool = False
    ) -> ApplyResponse:
        """
        Apply previously previewed changes.
        
        This:
        - Requires preview ID or confirmation token
        - Validates that preview hasn't expired
        - Applies changes atomically where possible
        - Returns success/failure status with detailed results
        - Logs all applied changes to audit trail
        
        Args:
            preview_id: The preview ID to apply
            confirmation: User confirmation (required for large operations)
            dry_run: If True, perform all validation but skip actual write
            
        Returns:
            ApplyResponse with results
        """
        logger.info(
            f"Applying changes from preview {preview_id} (dry_run={dry_run})"
        )
        
        # Retrieve preview from cache
        preview = self.preview_cache.get(preview_id)
        
        if not preview:
            return ApplyResponse(
                success=False,
                preview_id=preview_id,
                spreadsheet_id="",
                cells_updated=0,
                errors=["Preview not found or has expired. Please generate a new preview."],
            )
        
        # Apply changes
        result = await self.apply_engine.apply_changes(preview, confirmation, dry_run)
        
        # Remove from cache if successful and not dry-run
        if result.success and not dry_run:
            self.preview_cache.remove(preview_id)
            logger.info(f"Successfully applied {result.cells_updated} changes")
        elif result.success and dry_run:
            logger.info(f"Dry-run successful: would apply {result.cells_updated} changes")
        else:
            logger.warning(f"Failed to apply changes: {result.errors}")
        
        return result

    def cleanup_expired_previews(self) -> int:
        """
        Clean up expired previews from cache.
        
        Returns:
            Number of expired previews removed
        """
        count = self.preview_cache.cleanup_expired()
        if count > 0:
            logger.info(f"Cleaned up {count} expired previews")
        return count
    
    async def execute_with_safety(
        self,
        spreadsheet_id: str,
        operation: Operation,
        require_preview: bool = True
    ) -> PreviewResponse:
        """
        Execute operation with full safety checks (spec-compliant method).
        
        This method implements the complete safety workflow:
        1. Analyze scope of operation
        2. Run safety validation
        3. Block if not allowed
        4. Generate preview if required
        5. Log to audit trail
        
        Args:
            spreadsheet_id: The spreadsheet to operate on
            operation: The operation to execute
            require_preview: If True, always generate preview (default)
            
        Returns:
            PreviewResponse for user approval
            
        Raises:
            SafetyCheckFailedError: If operation violates safety constraints
        """
        start_time = time.time()
        
        logger.info(
            f"Executing operation with safety: {operation.operation_type} "
            f"on {spreadsheet_id}"
        )
        
        # 1. Generate preview to analyze scope
        preview = self.generate_preview(
            spreadsheet_id, operation, dry_run=True
        )
        
        # 2. Analyze scope from preview changes
        scope = self.scope_analyzer.analyze_from_changes(
            preview.changes, operation.operation_type.value
        )
        
        # 3. Run safety validation
        safety_check = self.safety_validator.validate_operation_with_scope(
            operation.operation_type.value,
            scope,
            dry_run=False
        )
        
        # 4. Block if not allowed
        if not safety_check.allowed:
            error_msg = "\n".join(safety_check.errors)
            logger.error(f"Safety check failed: {error_msg}")
            
            # Log failed attempt to audit trail
            await self._log_safety_failure(
                spreadsheet_id, operation, scope, safety_check.errors, time.time() - start_time
            )
            
            raise SafetyCheckFailedError(
                f"Operation blocked by safety checks:\n{error_msg}"
            )
        
        # 5. Generate full preview if required or requested
        if require_preview or safety_check.requires_preview:
            logger.info("Generating preview for user approval")
            preview = self.generate_preview(
                spreadsheet_id, operation, dry_run=False
            )
            
            # Log preview generation
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Preview generated successfully: {preview.preview_id} "
                f"({duration_ms:.2f}ms)"
            )
            
            return preview
        
        # If no preview required (should rarely happen), execute immediately
        logger.warning(
            "Executing operation without preview - this should be rare"
        )
        preview = self.generate_preview(
            spreadsheet_id, operation, dry_run=False
        )
        
        return preview
    
    async def _log_safety_failure(
        self,
        spreadsheet_id: str,
        operation: Operation,
        scope: OperationScope,
        errors: list[str],
        duration_seconds: float
    ):
        """Log a safety check failure to audit trail."""
        from ..engine.audit import AuditEntry
        from dataclasses import asdict
        
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            operation_type=operation.operation_type.value,
            spreadsheet_id=spreadsheet_id,
            user="system",
            preview_id=None,
            scope=asdict(scope),
            status="failed",
            changes_applied=0,
            errors=errors,
            duration_ms=duration_seconds * 1000
        )
        
        await self.audit_logger.log_operation(entry)
