"""API routes for SheetSmith."""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from ..ops import (
    DeterministicOpsEngine,
    SearchRequest,
    PreviewRequest,
    ApplyRequest,
)

router = APIRouter()

# Global ops engine instance
_ops_engine: Optional[DeterministicOpsEngine] = None


def get_ops_engine() -> DeterministicOpsEngine:
    """Get the global ops engine instance."""
    global _ops_engine
    if _ops_engine is None:
        from .app import get_agent
        agent = get_agent()
        _ops_engine = DeterministicOpsEngine(
            sheets_client=agent.sheets_client,
            memory_store=agent.memory_store,
        )
    return _ops_engine


def get_agent():
    """Get the global agent instance."""
    from .app import get_agent as _get_agent

    return _get_agent()


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    spreadsheet_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str
    conversation_length: int


class SpreadsheetInfoRequest(BaseModel):
    """Request for spreadsheet info."""

    spreadsheet_id: str


class FormulaSearchRequest(BaseModel):
    """Request for formula search."""

    spreadsheet_id: str
    pattern: str
    sheet_names: Optional[list[str]] = None
    case_sensitive: bool = False


class RangeReadRequest(BaseModel):
    """Request to read a range."""

    spreadsheet_id: str
    range_notation: str
    include_formulas: bool = True


class RuleCreateRequest(BaseModel):
    """Request to create a rule."""

    name: str
    description: str
    rule_type: str
    content: str
    examples: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class LogicBlockCreateRequest(BaseModel):
    """Request to create a logic block."""

    name: str
    block_type: str
    description: str
    formula_pattern: str
    variables: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


# Chat endpoints


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the SheetSmith agent."""
    agent = get_agent()

    # Add spreadsheet context if provided
    message = request.message
    if request.spreadsheet_id and "spreadsheet" not in message.lower():
        message = f"[Working with spreadsheet: {request.spreadsheet_id}]\n\n{message}"

    try:
        response = await agent.process_message(message)
        return ChatResponse(
            response=response,
            conversation_length=len(agent.messages),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/reset")
async def reset_chat():
    """Reset the conversation history."""
    agent = get_agent()
    agent.reset_conversation()
    return {"status": "ok", "message": "Conversation reset"}


# Google Sheets endpoints


@router.post("/sheets/info")
async def get_spreadsheet_info(request: SpreadsheetInfoRequest):
    """Get information about a spreadsheet."""
    agent = get_agent()
    try:
        info = agent.sheets_client.get_spreadsheet_info(request.spreadsheet_id)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sheets/read")
async def read_range(request: RangeReadRequest):
    """Read values and formulas from a range."""
    agent = get_agent()
    try:
        result = agent.sheets_client.read_range(
            request.spreadsheet_id,
            request.range_notation,
            request.include_formulas,
        )
        return {
            "spreadsheet_id": result.spreadsheet_id,
            "sheet_name": result.sheet_name,
            "range": result.range_notation,
            "cells": [
                {
                    "cell": c.cell,
                    "value": c.value,
                    "formula": c.formula,
                }
                for c in result.cells
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sheets/search")
async def search_formulas(request: FormulaSearchRequest):
    """Search for formulas matching a pattern."""
    agent = get_agent()
    try:
        matches = agent.sheets_client.search_formulas(
            request.spreadsheet_id,
            request.pattern,
            request.sheet_names,
            request.case_sensitive,
        )
        return {
            "pattern": request.pattern,
            "match_count": len(matches),
            "matches": [
                {
                    "sheet": m.sheet_name,
                    "cell": m.cell,
                    "formula": m.formula,
                    "matched_text": m.matched_text,
                }
                for m in matches
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Memory endpoints


@router.get("/rules")
async def list_rules(rule_type: Optional[str] = None):
    """List stored rules."""
    agent = get_agent()
    rules = await agent.memory_store.get_rules(rule_type)
    return {
        "count": len(rules),
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "rule_type": r.rule_type,
                "content": r.content,
                "tags": r.tags,
            }
            for r in rules
        ],
    }


@router.post("/rules")
async def create_rule(request: RuleCreateRequest):
    """Create a new rule."""
    from ..memory import Rule
    import uuid

    agent = get_agent()
    rule = Rule(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        rule_type=request.rule_type,
        content=request.content,
        examples=request.examples,
        tags=request.tags,
    )
    stored = await agent.memory_store.store_rule(rule)
    return {"id": stored.id, "message": "Rule created successfully"}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule."""
    agent = get_agent()
    deleted = await agent.memory_store.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "ok", "message": "Rule deleted"}


@router.get("/logic-blocks")
async def list_logic_blocks(block_type: Optional[str] = None):
    """List stored logic blocks."""
    agent = get_agent()
    blocks = await agent.memory_store.get_logic_blocks(block_type)
    return {
        "count": len(blocks),
        "blocks": [
            {
                "id": b.id,
                "name": b.name,
                "block_type": b.block_type,
                "description": b.description,
                "formula_pattern": b.formula_pattern,
                "tags": b.tags,
            }
            for b in blocks
        ],
    }


@router.post("/logic-blocks")
async def create_logic_block(request: LogicBlockCreateRequest):
    """Create a new logic block."""
    from ..memory import LogicBlock
    import uuid

    agent = get_agent()
    block = LogicBlock(
        id=str(uuid.uuid4()),
        name=request.name,
        block_type=request.block_type,
        description=request.description,
        formula_pattern=request.formula_pattern,
        variables=request.variables,
        tags=request.tags,
    )
    stored = await agent.memory_store.store_logic_block(block)
    return {"id": stored.id, "message": "Logic block created successfully"}


@router.get("/audit-logs")
async def list_audit_logs(spreadsheet_id: Optional[str] = None, limit: int = 50):
    """List audit logs."""
    agent = get_agent()
    logs = await agent.memory_store.get_audit_logs(spreadsheet_id, limit=limit)
    return {
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action,
                "spreadsheet_id": log.spreadsheet_id,
                "description": log.description,
                "changes_applied": log.changes_applied,
            }
            for log in logs
        ],
    }


# Health check


@router.get("/health")
async def health_check():
    """Health check endpoint with diagnostics."""
    from ..config import settings

    # Gather non-secret diagnostics
    config = {
        "llm_provider": settings.llm_provider,
        "model_name": settings.model_name,
        "anthropic_key_present": bool(settings.anthropic_api_key),
        "openrouter_key_present": bool(settings.openrouter_api_key),
        "google_credentials_configured": settings.google_credentials_path.exists(),
    }

    # Include openrouter_model when using OpenRouter provider
    if settings.llm_provider == "openrouter":
        config["openrouter_model"] = settings.openrouter_model

    diagnostics = {
        "status": "ok",
        "service": "sheetsmith",
        "config": config,
    }

    return diagnostics


@router.get("/config/limits")
async def get_config_limits():
    """Get safety limits and cost configuration."""
    from ..config import settings
    
    return {
        "safety_limits": {
            "max_cells_per_operation": settings.max_cells_per_operation,
            "max_sheets_per_operation": settings.max_sheets_per_operation,
            "max_formula_length": settings.max_formula_length,
            "require_preview_above_cells": settings.require_preview_above_cells,
        },
        "cost_info": {
            "deterministic_cost": 0.0,
            "ai_estimated_cost_min": 0.01,
            "ai_estimated_cost_max": 0.05,
        },
    }


# Cost tracking endpoints


@router.get("/costs/summary")
async def get_costs_summary():
    """Get cost summary for the current session."""
    agent = get_agent()
    try:
        summary = agent.get_cost_summary()
        return {
            "status": "ok",
            **summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/details")
async def get_costs_details(limit: int = 50):
    """Get detailed cost log entries."""
    agent = get_agent()
    try:
        recent_calls = agent.call_logger.get_recent_calls(limit=limit)
        return {
            "status": "ok",
            "calls": recent_calls,
            "count": len(recent_calls),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/costs/reset")
async def reset_costs():
    """Reset session cost tracking."""
    agent = get_agent()
    try:
        agent.reset_cost_tracking()
        return {
            "status": "ok",
            "message": "Cost tracking reset successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Deterministic Operations endpoints


@router.post("/ops/search")
async def ops_search(request: SearchRequest):
    """
    Search for cells matching criteria.
    
    This deterministic operation searches by:
    - Header name (never by column letter)
    - Row label/identifier
    - Formula pattern (exact or regex)
    - Value pattern
    
    No LLM usage - pure deterministic search.
    """
    ops_engine = get_ops_engine()
    try:
        result = ops_engine.search(
            spreadsheet_id=request.spreadsheet_id,
            criteria=request.criteria,
            limit=request.limit,
        )
        return {
            "matches": [
                {
                    "spreadsheet_id": m.spreadsheet_id,
                    "sheet_name": m.sheet_name,
                    "cell": m.cell,
                    "row": m.row,
                    "col": m.col,
                    "header": m.header,
                    "row_label": m.row_label,
                    "value": m.value,
                    "formula": m.formula,
                }
                for m in result.matches
            ],
            "total_count": result.total_count,
            "searched_sheets": result.searched_sheets,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ops/preview")
async def ops_preview(request: PreviewRequest):
    """
    Generate preview of proposed changes.
    
    Shows:
    - Before/after values for each affected cell
    - Clear scope summary (sheets, cells, headers affected)
    - Location info for every change
    
    Returns a preview_id for use with /ops/apply.
    """
    ops_engine = get_ops_engine()
    try:
        preview = ops_engine.generate_preview(
            spreadsheet_id=request.spreadsheet_id,
            operation=request.operation,
        )
        return {
            "preview_id": preview.preview_id,
            "spreadsheet_id": preview.spreadsheet_id,
            "operation_type": preview.operation_type.value,
            "description": preview.description,
            "changes": [
                {
                    "sheet_name": c.sheet_name,
                    "cell": c.cell,
                    "old_value": c.old_value,
                    "old_formula": c.old_formula,
                    "new_value": c.new_value,
                    "new_formula": c.new_formula,
                    "header": c.header,
                    "row_label": c.row_label,
                }
                for c in preview.changes
            ],
            "scope": {
                "total_cells": preview.scope.total_cells,
                "affected_sheets": preview.scope.affected_sheets,
                "affected_headers": preview.scope.affected_headers,
                "sheet_count": preview.scope.sheet_count,
                "requires_approval": preview.scope.requires_approval,
            },
            "diff_text": preview.diff_text,
            "created_at": preview.created_at.isoformat(),
            "expires_at": preview.expires_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ops/apply")
async def ops_apply(request: ApplyRequest):
    """
    Apply previously previewed changes.
    
    Requires:
    - preview_id from /ops/preview
    - confirmation=true for operations affecting many cells
    
    Validates:
    - Preview hasn't expired
    - Safety limits are respected
    
    Returns:
    - Success status
    - Number of cells updated
    - Audit log ID
    """
    ops_engine = get_ops_engine()
    try:
        result = await ops_engine.apply_changes(
            preview_id=request.preview_id,
            confirmation=request.confirmation,
        )
        return {
            "success": result.success,
            "preview_id": result.preview_id,
            "spreadsheet_id": result.spreadsheet_id,
            "cells_updated": result.cells_updated,
            "errors": result.errors,
            "audit_log_id": result.audit_log_id,
            "applied_at": result.applied_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Header-Based Mapping endpoints

# Global mapping manager instance
_mapping_manager: Optional["MappingManager"] = None


def get_mapping_manager():
    """Get the global mapping manager instance."""
    global _mapping_manager
    if _mapping_manager is None:
        from ..mapping import MappingManager
        agent = get_agent()
        _mapping_manager = MappingManager(sheets_client=agent.sheets_client)
    return _mapping_manager


class ValidateMappingRequest(BaseModel):
    """Request to validate a specific mapping."""
    
    mapping_id: int
    mapping_type: str = "column"  # "column" or "cell"


@router.get("/mappings/{spreadsheet_id}/audit")
async def audit_mappings(spreadsheet_id: str):
    """
    Audit all mappings for a spreadsheet.
    
    Returns health status of all cached mappings:
    - ✅ valid: Header exists in expected position
    - ⚠️ moved: Header exists but in different position
    - ❌ missing: Header not found in sheet
    - ⚠️ ambiguous: Multiple columns with same header
    """
    manager = get_mapping_manager()
    
    # Ensure manager is initialized
    if not manager._initialized:
        await manager.initialize()
    
    try:
        report = await manager.audit_mappings(spreadsheet_id)
        return {
            "spreadsheet_id": report.spreadsheet_id,
            "spreadsheet_title": report.spreadsheet_title,
            "total_mappings": report.total_mappings,
            "summary": {
                "valid": report.valid_count,
                "moved": report.moved_count,
                "missing": report.missing_count,
                "ambiguous": report.ambiguous_count,
            },
            "entries": [
                {
                    "mapping_id": entry.mapping_id,
                    "mapping_type": entry.mapping_type,
                    "sheet_name": entry.sheet_name,
                    "header_text": entry.header_text,
                    "row_label": entry.row_label,
                    "current_address": entry.current_address,
                    "status": entry.status.value,
                    "needs_action": entry.needs_action,
                    "last_validated_at": (
                        entry.last_validated_at.isoformat()
                        if entry.last_validated_at
                        else None
                    ),
                }
                for entry in report.entries
            ],
            "generated_at": report.generated_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mappings/disambiguate")
async def disambiguate_column(request: "DisambiguationResponse"):
    """
    Store user's column disambiguation choice.
    
    When multiple columns share the same header, the system returns a
    disambiguation request. Use this endpoint to specify which column to use.
    
    The request_id comes from the DisambiguationRequiredError, and
    selected_column_index is the index in the candidates array.
    """
    from ..mapping import DisambiguationResponse
    
    manager = get_mapping_manager()
    
    # Ensure manager is initialized
    if not manager._initialized:
        await manager.initialize()
    
    try:
        mapping = await manager.store_disambiguation(request)
        return {
            "success": True,
            "mapping": {
                "id": mapping.id,
                "spreadsheet_id": mapping.spreadsheet_id,
                "sheet_name": mapping.sheet_name,
                "header_text": mapping.header_text,
                "column_letter": mapping.column_letter,
                "column_index": mapping.column_index,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mappings/{mapping_id}")
async def delete_mapping(mapping_id: int, mapping_type: str = "column"):
    """
    Delete a mapping.
    
    Args:
        mapping_id: The mapping ID to delete
        mapping_type: "column" or "cell" (default: "column")
    """
    manager = get_mapping_manager()
    
    # Ensure manager is initialized
    if not manager._initialized:
        await manager.initialize()
    
    try:
        deleted = await manager.delete_mapping(mapping_id, mapping_type)
        if not deleted:
            raise HTTPException(status_code=404, detail="Mapping not found")
        return {"status": "ok", "message": "Mapping deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mappings/validate")
async def validate_mapping(request: ValidateMappingRequest):
    """
    Validate a specific mapping.
    
    Checks if the mapping is still accurate and returns current status.
    """
    manager = get_mapping_manager()
    
    # Ensure manager is initialized
    if not manager._initialized:
        await manager.initialize()
    
    try:
        result = await manager.validate_mapping(
            request.mapping_id, request.mapping_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
