"""Main deterministic operations engine."""

import logging
from typing import Optional

from ..sheets import GoogleSheetsClient
from ..memory import MemoryStore
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
        
        # Preview cache
        self.preview_cache = PreviewCache(default_ttl_minutes=30)
        
        logger.info("DeterministicOpsEngine initialized")

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
        self, spreadsheet_id: str, operation: Operation, ttl_minutes: int = 30
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
            
        Returns:
            PreviewResponse with changes and metadata
        """
        logger.info(f"Generating preview for {operation.operation_type} on {spreadsheet_id}")
        
        preview = self.preview_generator.generate_preview(
            spreadsheet_id, operation, ttl_minutes
        )
        
        # Store in cache
        self.preview_cache.store(preview, ttl_minutes)
        
        logger.info(
            f"Preview generated: {preview.preview_id} - "
            f"{preview.scope.total_cells} cells affected in "
            f"{preview.scope.sheet_count} sheets"
        )
        
        return preview

    async def apply_changes(self, preview_id: str, confirmation: bool = False) -> ApplyResponse:
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
            
        Returns:
            ApplyResponse with results
        """
        logger.info(f"Applying changes from preview {preview_id}")
        
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
        result = await self.apply_engine.apply_changes(preview, confirmation)
        
        # Remove from cache if successful
        if result.success:
            self.preview_cache.remove(preview_id)
            logger.info(f"Successfully applied {result.cells_updated} changes")
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
