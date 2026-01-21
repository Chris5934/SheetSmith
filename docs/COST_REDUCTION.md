# LLM Cost Reduction Guide

This document explains the cost reduction features implemented in SheetSmith and how to use them effectively.

## Overview

SheetSmith has been optimized to minimize LLM API costs while maintaining full functionality. The system can reduce costs by 75-95% compared to the baseline configuration by:

1. **Removing tool schemas** from most LLM calls
2. **Using minimal system prompts** based on operation type
3. **Limiting conversation history** to only what's needed
4. **Setting appropriate max_tokens** for each operation type
5. **Using cheaper models** for simple operations
6. **Enforcing hard limits** on payload sizes
7. **Per-operation budget guards** to prevent runaway costs

## Configuration

### Quick Start: Enable Cost Reduction

Add these settings to your `.env` file:

```bash
# Enable JSON-only mode (removes tool schemas)
USE_JSON_MODE=true

# Use cheaper models for non-complex operations
PARSER_MODEL=anthropic/claude-3-haiku
AI_ASSIST_MODEL=anthropic/claude-3-haiku

# Set appropriate token limits
PARSER_MAX_TOKENS=300
AI_ASSIST_MAX_TOKENS=400
PLANNING_MAX_TOKENS=800

# Hard caps for safety
PROMPT_MAX_CHARS=10000
SPREADSHEET_CONTENT_MAX_CHARS=5000
```

### Operation Types

SheetSmith automatically detects the operation type from user messages:

- **Parser**: Simple operations like "replace X with Y"
  - Uses: Haiku model, 300 tokens, no history, minimal prompt
  - Cost: ~$0.0001-0.0005 per operation

- **AI Assist**: Clarifying questions or simple help
  - Uses: Haiku model, 400 tokens, last 6 messages, minimal prompt
  - Cost: ~$0.001-0.005 per operation

- **Planning**: Complex operations requiring analysis
  - Uses: Main model, 800 tokens, last 10 messages, planning prompt
  - Cost: ~$0.01-0.05 per operation

- **Tool Continuation**: Following up after tool use
  - Uses: Main model, 600 tokens, last 10 messages, tools included
  - Cost: ~$0.005-0.02 per operation

### Detailed Configuration Options

#### JSON Mode vs Tool Mode

```bash
# JSON Mode (Recommended for cost reduction)
USE_JSON_MODE=true
# LLM outputs structured JSON without tool schemas
# Reduces input tokens by 50-80%

# Tool Mode (Legacy behavior)
USE_JSON_MODE=false
# Sends full tool schemas on every call
# Higher cost but more robust
```

#### Model Selection

```bash
# For Anthropic direct (LLM_PROVIDER=anthropic)
MODEL_NAME=claude-sonnet-4-20250514
PARSER_MODEL=claude-3-haiku-20240307
AI_ASSIST_MODEL=claude-3-haiku-20240307

# For OpenRouter (LLM_PROVIDER=openrouter)
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
PARSER_MODEL=anthropic/claude-3-haiku
AI_ASSIST_MODEL=anthropic/claude-3-haiku

# Use free models when available (OpenRouter only)
USE_FREE_MODELS=true
# Adds :free suffix to model names
```

#### Token Limits

```bash
# Maximum tokens to generate per operation type
PARSER_MAX_TOKENS=300        # Just need JSON output
AI_ASSIST_MAX_TOKENS=400     # Brief clarifications
PLANNING_MAX_TOKENS=800      # More complex reasoning

# Legacy default (not recommended)
MAX_TOKENS=4096              # Too high for most operations
```

#### Hard Caps

```bash
# Maximum characters in total prompt (includes system + messages)
PROMPT_MAX_CHARS=10000

# Maximum characters of spreadsheet content to include in prompts
SPREADSHEET_CONTENT_MAX_CHARS=5000

# Maximum formula examples to send in a single request
FORMULA_SAMPLE_LIMIT=5
```

#### Budget Limits

```bash
# Enable cost tracking and logging
ENABLE_COST_LOGGING=true
COST_LOG_PATH=logs/llm_costs.jsonl

# Maximum cost per individual request (in cents)
PER_REQUEST_BUDGET_CENTS=5.0

# Maximum cost per session (in cents)
SESSION_BUDGET_CENTS=50.0

# Alert threshold for high-cost requests (in cents)
ALERT_ON_HIGH_COST=true
HIGH_COST_THRESHOLD_CENTS=1.0
```

## Cost Analysis

### Before Optimization

Typical operation with full tool schemas:
- Input tokens: ~2000 (tools: 1200, history: 500, system: 300)
- Output tokens: ~500
- Model: Claude Sonnet 4
- Cost per operation: **$0.015-0.030**

### After Optimization

Same operation with cost reduction enabled:

**Parser Operation** (replace/update):
- Input tokens: ~200 (no tools, minimal history, small prompt)
- Output tokens: ~150
- Model: Claude Haiku
- Cost per operation: **$0.0001-0.0005**
- **Savings: 95-99%**

**AI Assist Operation** (clarification):
- Input tokens: ~400 (no tools, last 6 messages, small prompt)
- Output tokens: ~200
- Model: Claude Haiku
- Cost per operation: **$0.001-0.003**
- **Savings: 85-95%**

**Planning Operation** (complex analysis):
- Input tokens: ~800 (with tools, last 10 messages, planning prompt)
- Output tokens: ~500
- Model: Claude Sonnet 4
- Cost per operation: **$0.005-0.015**
- **Savings: 50-70%**

### Bulk Operations

Updating 100 formulas:

- **Before**: 100 operations × $0.020 = **$2.00**
- **After**: 100 operations × $0.0003 = **$0.03**
- **Savings: 98.5%**

## System Prompts

The system uses different prompts based on operation type:

### Parser Prompt (~200 chars)
```
You are a JSON command generator for spreadsheet operations.
Output only valid JSON with operation type and parameters.
Available operations: replace_in_formulas, set_value_by_header, search_formulas.
Be concise. No explanations.
```

### AI Assist Prompt (~250 chars)
```
You help users specify spreadsheet operations.
Ask clarifying questions if ambiguous.
Output operation JSON when clear.
Keep responses under 3 sentences.
```

### Planning Prompt (~500 chars)
```
You are SheetSmith, an AI assistant for Google Sheets formulas.
Understand user intent, search formulas, propose changes with diffs.
Always preview changes before applying. Use tools efficiently.
Prefer formula.mass_replace for simple text replacements.
Maximum 5 sentences per response unless showing results.
```

## Conversation History Management

History is automatically limited based on operation type:

- **Parser**: Only current message (stateless)
- **AI Assist**: Last 6 messages (2-3 exchanges)
- **Planning**: Last 10 messages
- **Tool Continuation**: Last 10 messages

This prevents context window bloat while maintaining necessary context.

## Budget Guards

The system enforces budget limits at multiple levels:

### Per-Operation Budgets

Hard-coded limits prevent expensive operations:

```python
OPERATION_BUDGETS = {
    "parser": 0.001 cents,           # $0.00001
    "ai_assist": 0.01 cents,         # $0.0001
    "planning": 0.05 cents,          # $0.0005
    "tool_continuation": 0.02 cents, # $0.0002
}
```

If an operation would exceed its budget, it's rejected before the API call.

### Session Budgets

Tracks cumulative cost across all operations in a session:

```bash
# Stop processing if session cost exceeds this
SESSION_BUDGET_CENTS=50.0
```

### Request Budgets

Per-request maximum to prevent single expensive calls:

```bash
# Reject any single request over this cost
PER_REQUEST_BUDGET_CENTS=5.0
```

## Monitoring Costs

### View Cost Logs

Cost logs are written to `logs/llm_costs.jsonl`:

```bash
# View recent costs
tail -n 20 logs/llm_costs.jsonl | jq

# Sum total cost for today
grep $(date +%Y-%m-%d) logs/llm_costs.jsonl | jq -s 'map(.cost_cents) | add'
```

### Cost Summary API

Get cost summary via API (when running the server):

```bash
curl http://localhost:8000/cost-summary
```

Returns:
```json
{
  "total_calls": 15,
  "total_cost_cents": 0.45,
  "total_input_tokens": 3500,
  "total_output_tokens": 1200,
  "budget_status": {
    "session_cost_cents": 0.45,
    "session_budget_cents": 50.0,
    "remaining_budget_cents": 49.55,
    "budget_used_percent": 0.9
  }
}
```

## Best Practices

### 1. Enable JSON Mode

Always use `USE_JSON_MODE=true` unless you encounter issues. Tool schemas add 1000-2000 tokens per request.

### 2. Use Haiku for Simple Operations

Set `PARSER_MODEL` and `AI_ASSIST_MODEL` to Haiku. It's 10-20x cheaper than Sonnet for simple tasks.

### 3. Set Appropriate Token Limits

Don't use `MAX_TOKENS=4096` for everything. Most operations need 300-800 tokens.

### 4. Monitor Your Costs

Enable `ENABLE_COST_LOGGING=true` and review logs regularly to identify expensive patterns.

### 5. Use Hard Caps

Set `PROMPT_MAX_CHARS` and `SESSION_BUDGET_CENTS` to prevent runaway costs.

## Troubleshooting

### Operations Rejected for Budget

If you see "Budget exceeded" errors:

1. Check your session budget: `SESSION_BUDGET_CENTS`
2. Review recent costs: `tail logs/llm_costs.jsonl`
3. Reset session or increase budget if needed
4. Consider splitting large operations

### JSON Mode Issues

If JSON mode causes problems:

1. Temporarily disable: `USE_JSON_MODE=false`
2. Check which operation type is failing
3. Report the issue for investigation
4. Tool mode will work but cost more

### High Costs Despite Settings

If costs are still high:

1. Verify environment variables are loaded
2. Check operation type detection is working
3. Review cost logs for unexpected patterns
4. Ensure conversation history is being limited

## Migration from Previous Version

If upgrading from a version without cost reduction:

1. Copy new settings from `.env.example`
2. Enable JSON mode: `USE_JSON_MODE=true`
3. Set Haiku models for parser and assist
4. Set token limits for each operation type
5. Monitor costs for first few operations
6. Adjust limits based on your usage

## Summary

With all cost reduction features enabled, you can expect:

- **95%+ savings** on simple parser operations
- **85-95% savings** on AI assist operations
- **50-70% savings** on complex planning operations
- **Overall: 75-90% cost reduction** for typical usage

The system maintains full functionality while dramatically reducing costs through intelligent resource management.
