"""Preview cache management."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from .models import PreviewResponse


class PreviewCache:
    """In-memory cache for operation previews.
    
    Thread-safe implementation using asyncio.Lock for concurrent access.
    """

    def __init__(self, default_ttl_minutes: int = 30):
        self._cache: dict[str, PreviewResponse] = {}
        self._default_ttl = default_ttl_minutes
        self._lock = asyncio.Lock()

    def store(self, preview: PreviewResponse, ttl_minutes: Optional[int] = None) -> str:
        """
        Store a preview in the cache.
        
        Args:
            preview: The preview to store
            ttl_minutes: Time to live in minutes (uses default if not specified)
            
        Returns:
            The preview ID
        """
        if not preview.preview_id:
            preview.preview_id = str(uuid.uuid4())
        
        ttl = ttl_minutes or self._default_ttl
        preview.expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl)
        
        self._cache[preview.preview_id] = preview
        return preview.preview_id

    async def store_async(self, preview: PreviewResponse, ttl_minutes: Optional[int] = None) -> str:
        """Thread-safe async version of store."""
        async with self._lock:
            return self.store(preview, ttl_minutes)

    def get(self, preview_id: str) -> Optional[PreviewResponse]:
        """
        Retrieve a preview from the cache.
        
        Args:
            preview_id: The preview ID to retrieve
            
        Returns:
            The preview if found and not expired, None otherwise
        """
        preview = self._cache.get(preview_id)
        
        if preview is None:
            return None
        
        # Check expiration
        if datetime.now(timezone.utc) > preview.expires_at:
            # Remove expired preview
            del self._cache[preview_id]
            return None
        
        return preview

    async def get_async(self, preview_id: str) -> Optional[PreviewResponse]:
        """Thread-safe async version of get."""
        async with self._lock:
            return self.get(preview_id)

    def remove(self, preview_id: str) -> bool:
        """
        Remove a preview from the cache.
        
        Args:
            preview_id: The preview ID to remove
            
        Returns:
            True if removed, False if not found
        """
        if preview_id in self._cache:
            del self._cache[preview_id]
            return True
        return False

    async def remove_async(self, preview_id: str) -> bool:
        """Thread-safe async version of remove."""
        async with self._lock:
            return self.remove(preview_id)

    def cleanup_expired(self) -> int:
        """
        Remove all expired previews from the cache.
        
        Returns:
            Number of expired previews removed
        """
        now = datetime.now(timezone.utc)
        expired_ids = [
            preview_id
            for preview_id, preview in self._cache.items()
            if now > preview.expires_at
        ]
        
        for preview_id in expired_ids:
            del self._cache[preview_id]
        
        return len(expired_ids)

    async def cleanup_expired_async(self) -> int:
        """Thread-safe async version of cleanup_expired."""
        async with self._lock:
            return self.cleanup_expired()

    def clear(self):
        """Clear all previews from the cache."""
        self._cache.clear()

    async def clear_async(self):
        """Thread-safe async version of clear."""
        async with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get the current cache size."""
        return len(self._cache)
