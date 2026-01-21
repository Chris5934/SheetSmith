"""Optional LLM-assisted disambiguation for ambiguous placeholders."""

import logging
from typing import Optional

from .models import MappingSuggestion

logger = logging.getLogger(__name__)


class PlaceholderAssistant:
    """LLM-assisted disambiguation for unclear placeholders."""

    def __init__(self, llm_client: Optional[object] = None):
        """
        Initialize the placeholder assistant.

        Args:
            llm_client: Optional LLM client for making suggestions
        """
        self.llm_client = llm_client

    async def suggest_mapping(
        self,
        placeholder: str,
        available_headers: list[str],
    ) -> list[MappingSuggestion]:
        """
        Use LLM to suggest which header best matches a placeholder.

        This is only called when placeholders are ambiguous and deterministic
        matching cannot resolve them.

        Args:
            placeholder: The placeholder name (e.g., "base_damage")
            available_headers: List of available header texts

        Returns:
            List of MappingSuggestion objects, sorted by confidence
        """
        if not self.llm_client:
            logger.warning("No LLM client available, cannot suggest mappings")
            return []

        # TODO: Implement LLM-based suggestion
        # For now, return empty list as LLM assistance is optional
        logger.info(
            f"LLM suggestion requested for placeholder '{placeholder}' "
            f"with {len(available_headers)} available headers"
        )

        # Placeholder implementation - would call LLM with a minimal prompt like:
        # "Given placeholder name '{placeholder}' and available headers {headers},
        #  which header is the best match? Respond with just the header name."

        return []

    async def clarify_intent(
        self,
        formula: str,
        ambiguous_placeholders: list[str],
    ) -> dict[str, str]:
        """
        Ask LLM to clarify user intent for ambiguous placeholders.

        This generates a clarification request that can be presented to the user
        or used to make an informed guess.

        Args:
            formula: The original formula with placeholders
            ambiguous_placeholders: List of ambiguous placeholder syntaxes

        Returns:
            Dict mapping placeholder to clarification question
        """
        if not self.llm_client:
            logger.warning("No LLM client available, cannot clarify intent")
            return {}

        # TODO: Implement LLM-based clarification
        # For now, return empty dict as LLM assistance is optional
        logger.info(
            f"Clarification requested for formula '{formula}' "
            f"with ambiguous placeholders: {ambiguous_placeholders}"
        )

        # Placeholder implementation - would call LLM with a prompt like:
        # "This formula has ambiguous placeholders: {placeholders}.
        #  What questions should we ask the user to clarify their intent?"

        return {}
