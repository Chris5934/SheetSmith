"""Router for directing operations to deterministic or AI-assist handlers."""

import logging
from typing import Optional, TYPE_CHECKING

from . import (
    OperationMode,
    OperationRequest,
    DeterministicReplaceRequest,
    SetValueRequest,
    AIAssistRequest,
)
from ..ops import (
    DeterministicOpsEngine,
    PreviewRequest,
    PreviewResponse,
    OperationType,
)
from ..ops.models import SearchCriteria, Operation

if TYPE_CHECKING:
    from ..agent import SheetSmithAgent

logger = logging.getLogger(__name__)


class ModeRouter:
    """Routes operations to deterministic or AI-assist handlers."""

    def __init__(
        self,
        ops_engine: DeterministicOpsEngine,
        ai_agent: Optional["SheetSmithAgent"] = None,
    ):
        """
        Initialize the mode router.
        
        Args:
            ops_engine: Deterministic operations engine
            ai_agent: Optional AI agent for AI-assist mode
        """
        self.ops_engine = ops_engine
        self.ai_agent = ai_agent
        logger.info("ModeRouter initialized")

    async def route_operation(self, request: OperationRequest) -> PreviewResponse:
        """
        Route operation to appropriate handler based on mode.
        
        Args:
            request: Operation request with mode and parameters
            
        Returns:
            PreviewResponse with changes to be applied
        """
        logger.info(f"Routing operation: {request.operation_type} in {request.mode} mode")
        
        if request.mode == OperationMode.DETERMINISTIC:
            return await self._handle_deterministic(request)
        else:
            return await self._handle_ai_assist(request)

    async def _handle_deterministic(self, request: OperationRequest) -> PreviewResponse:
        """
        Handle operation deterministically - no LLM.
        
        Args:
            request: Operation request with parameters
            
        Returns:
            PreviewResponse with validated changes
        """
        logger.info(f"Handling deterministic operation: {request.operation_type}")
        
        # Validate parameters are unambiguous
        if not self._validate_deterministic_params(request):
            raise ValueError("Parameters are ambiguous or incomplete for deterministic mode")
        
        # Convert generic request to PreviewRequest
        preview_request = self._build_preview_request(request)
        
        # Call ops engine directly
        preview = await self.ops_engine.preview(
            preview_request.spreadsheet_id,
            preview_request.operation
        )
        
        logger.info(f"Deterministic preview generated: {len(preview.changes)} changes")
        return preview

    async def _handle_ai_assist(self, request: OperationRequest) -> PreviewResponse:
        """
        Handle operation with AI assistance.
        
        Args:
            request: Operation request with natural language description
            
        Returns:
            PreviewResponse after AI interpretation
        """
        if self.ai_agent is None:
            raise ValueError("AI agent not available for AI-assist mode")
        
        logger.info("Handling AI-assist operation")
        
        # Use AI to resolve ambiguities and convert to deterministic operation
        # This is a placeholder - would integrate with existing AI agent
        raise NotImplementedError("AI-assist mode not yet implemented")

    def _validate_deterministic_params(self, request: OperationRequest) -> bool:
        """
        Validate that parameters are unambiguous for deterministic execution.
        
        Args:
            request: Operation request to validate
            
        Returns:
            True if parameters are valid and unambiguous
        """
        params = request.parameters
        op_type = request.operation_type
        
        # Check required parameters based on operation type
        if op_type == "replace_in_formulas":
            required = ["header_text", "find", "replace"]
            return all(params.get(key) for key in required)
        
        elif op_type == "set_value_by_header":
            required = ["sheet_name", "header", "row_label", "value"]
            return all(params.get(key) is not None for key in required)
        
        return False

    def _build_preview_request(self, request: OperationRequest) -> PreviewRequest:
        """
        Build a PreviewRequest from a generic OperationRequest.
        
        Args:
            request: Generic operation request
            
        Returns:
            PreviewRequest for ops engine
        """
        params = request.parameters
        
        # Build search criteria based on operation type
        if request.operation_type == "replace_in_formulas":
            criteria = SearchCriteria(
                header_text=params.get("header_text"),
                formula_pattern=params.get("find"),
                case_sensitive=params.get("case_sensitive", False),
                is_regex=params.get("is_regex", False),
                sheet_names=params.get("sheet_names"),
            )
            
            operation = Operation(
                operation_type=OperationType.REPLACE_IN_FORMULAS,
                description=f"Replace '{params.get('find')}' with '{params.get('replace')}' in formulas under '{params.get('header_text')}'",
                search_criteria=criteria,
                find_pattern=params.get("find"),
                replace_with=params.get("replace"),
            )
        
        elif request.operation_type == "set_value_by_header":
            criteria = SearchCriteria(
                header_text=params.get("header"),
                row_label=params.get("row_label"),
                sheet_names=[params.get("sheet_name")] if params.get("sheet_name") else None,
            )
            
            operation = Operation(
                operation_type=OperationType.SET_VALUE_BY_HEADER,
                description=f"Set value at '{params.get('header')}' and row '{params.get('row_label')}' to '{params.get('value')}'",
                search_criteria=criteria,
                header_name=params.get("header"),
                row_labels=[params.get("row_label")],
                new_values={params.get("row_label"): params.get("value")},
            )
        
        else:
            raise ValueError(f"Unsupported operation type: {request.operation_type}")
        
        return PreviewRequest(
            spreadsheet_id=request.spreadsheet_id,
            operation=operation,
        )


__all__ = ["ModeRouter"]
