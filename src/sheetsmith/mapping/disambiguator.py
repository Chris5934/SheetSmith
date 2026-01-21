"""Disambiguation request handling for ambiguous header mappings."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from .models import (
    DisambiguationRequest,
    DisambiguationResponse,
    ColumnCandidate,
    ColumnMapping,
)

logger = logging.getLogger(__name__)


class DisambiguationHandler:
    """Manages disambiguation requests for ambiguous column headers."""

    def __init__(self):
        # In-memory storage for pending disambiguation requests
        # In production, this would be persisted to database
        self._pending_requests: dict[str, DisambiguationRequest] = {}
        self._request_ttl = timedelta(hours=24)

    def create_disambiguation_request(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        header_text: str,
        candidates: list[ColumnCandidate],
    ) -> DisambiguationRequest:
        """
        Create a new disambiguation request.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: The sheet name
            header_text: The ambiguous header text
            candidates: List of column candidates

        Returns:
            DisambiguationRequest with a unique request_id
        """
        request_id = str(uuid.uuid4())
        request = DisambiguationRequest(
            request_id=request_id,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            header_text=header_text,
            candidates=candidates,
        )

        self._pending_requests[request_id] = request
        logger.info(
            f"Created disambiguation request {request_id} for header "
            f"'{header_text}' with {len(candidates)} candidates"
        )

        return request

    def get_disambiguation_request(self, request_id: str) -> Optional[DisambiguationRequest]:
        """
        Get a pending disambiguation request by ID.

        Returns None if request not found or expired.
        """
        request = self._pending_requests.get(request_id)

        if request is None:
            return None

        # Check if request has expired
        if datetime.utcnow() - request.created_at > self._request_ttl:
            logger.info(f"Disambiguation request {request_id} has expired")
            del self._pending_requests[request_id]
            return None

        return request

    def resolve_disambiguation(
        self,
        response: DisambiguationResponse,
    ) -> ColumnCandidate:
        """
        Resolve a disambiguation request with user's choice.

        Args:
            response: User's disambiguation response

        Returns:
            The selected ColumnCandidate

        Raises:
            ValueError: If request not found or selected index is invalid
        """
        request = self.get_disambiguation_request(response.request_id)

        if request is None:
            raise ValueError(f"Disambiguation request {response.request_id} not found or expired")

        if response.selected_column_index < 0 or response.selected_column_index >= len(
            request.candidates
        ):
            raise ValueError(
                f"Invalid column index {response.selected_column_index}. "
                f"Must be between 0 and {len(request.candidates) - 1}"
            )

        selected = request.candidates[response.selected_column_index]

        logger.info(
            f"Resolved disambiguation request {response.request_id}: "
            f"selected column {selected.column_letter}"
        )

        # Remove the resolved request
        del self._pending_requests[response.request_id]

        return selected

    def create_mapping_from_resolution(
        self,
        request: DisambiguationRequest,
        response: DisambiguationResponse,
        selected: ColumnCandidate,
    ) -> ColumnMapping:
        """
        Create a ColumnMapping from a resolved disambiguation.

        Args:
            request: The original disambiguation request
            response: User's response
            selected: The selected column candidate

        Returns:
            ColumnMapping with disambiguation context
        """
        disambiguation_context = {
            "disambiguated_at": datetime.utcnow().isoformat(),
            "selected_index": response.selected_column_index,
            "user_label": response.user_label,
            "total_candidates": len(request.candidates),
        }

        mapping = ColumnMapping(
            spreadsheet_id=request.spreadsheet_id,
            sheet_name=request.sheet_name,
            header_text=request.header_text,
            column_letter=selected.column_letter,
            column_index=selected.column_index,
            header_row=selected.header_row,
            disambiguation_context=disambiguation_context,
            last_validated_at=datetime.utcnow(),
        )

        return mapping

    def cleanup_expired_requests(self) -> int:
        """
        Clean up expired disambiguation requests.

        Returns:
            Number of expired requests removed
        """
        now = datetime.utcnow()
        expired = [
            request_id
            for request_id, request in self._pending_requests.items()
            if now - request.created_at > self._request_ttl
        ]

        for request_id in expired:
            del self._pending_requests[request_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired disambiguation requests")

        return len(expired)

    def get_pending_requests_count(self) -> int:
        """Get the number of pending disambiguation requests."""
        return len(self._pending_requests)

    def get_all_pending_requests(self) -> list[DisambiguationRequest]:
        """Get all pending disambiguation requests."""
        return list(self._pending_requests.values())
