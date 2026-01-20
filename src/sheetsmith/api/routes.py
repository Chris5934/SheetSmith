"""API routes for SheetSmith."""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter()


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


class SearchRequest(BaseModel):
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
async def search_formulas(request: SearchRequest):
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
