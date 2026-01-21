# LLM Diagnostics and Cost Spike Detection

## Overview

SheetSmith includes comprehensive debugging tools and spike protection mechanisms to detect, diagnose, and prevent unexpected LLM cost increases. Every LLM call is automatically monitored and validated against a checklist of cost and performance criteria.

## Features

### 1. Pre-Call Validation

Before each LLM call, the system validates:

- **Model String**: Confirms correct model is being used
- **Tools Schema**: Checks if tools JSON is present (not recommended for efficiency)
- **System Prompt Size**: Validates prompt stays within reasonable limits (default: 500 chars)
- **Chat History Length**: Ensures minimal history for parser/helper calls
- **Sheet Content**: Detects unnecessary spreadsheet content in prompts
- **Max Tokens**: Confirms appropriate max_tokens for operation type

### 2. Post-Call Analysis

After each LLM call, the system analyzes:

- **Usage Data**: Logs actual input/output tokens from API
- **Cost Tracking**: Compares estimated vs. actual cost
- **Cost Spike Detection**: Alerts if cost exceeds expected thresholds
- **Duration Monitoring**: Tracks call latency

### 3. Cost Spike Detection

The system maintains expected cost ranges by operation type:

- **Parser**: ~0.1 cents (0.001 USD)
- **Helper/AI Assist**: ~0.3-1.0 cents (0.003-0.01 USD)
- **Planning**: ~5.0 cents (0.05 USD)
- **Full Agent**: ~5.0 cents (0.05 USD)

Costs exceeding 2x the expected amount trigger alerts.

## Configuration

Add these settings to your `.env` file:

```bash
# Diagnostic thresholds
MAX_SYSTEM_PROMPT_CHARS=500
MAX_HISTORY_MESSAGES=10
MAX_SHEET_CONTENT_CHARS=5000
MAX_TOOLS_SCHEMA_BYTES=0  # 0 = no tools allowed

# Cost spike detection
ENABLE_COST_SPIKE_DETECTION=true
COST_SPIKE_THRESHOLD_MULTIPLIER=2.0

# OpenRouter usage tracking
OPENROUTER_INCLUDE_USAGE=true
```

## API Endpoints

### Get LLM Call History

```http
GET /diagnostics/llm-calls?limit=100&operation_type=parser&spike_only=false
```

Returns historical diagnostic data for LLM calls.

**Query Parameters:**
- `limit` (int): Maximum records to return (1-1000, default: 100)
- `operation_type` (string, optional): Filter by operation type
- `spike_only` (bool): Only return calls that triggered cost spikes

**Response:**
```json
{
  "calls": [
    {
      "timestamp": "2026-01-21T12:34:56Z",
      "operation": "parser",
      "model": "anthropic/claude-3.5-sonnet:free",
      "duration_ms": 245,
      "input_tokens": 150,
      "output_tokens": 50,
      "estimated_cost_usd": 0.001,
      "actual_cost_usd": 0.0009,
      "is_spike": false,
      "validation": {
        "model_ok": true,
        "tools_ok": true,
        "prompt_size_ok": true,
        "history_ok": true,
        "max_tokens_ok": true
      },
      "warnings": []
    }
  ],
  "total": 1
}
```

### Get Cost Summary

```http
GET /diagnostics/cost-summary
```

Returns cost summary and budget status.

**Response:**
```json
{
  "session_summary": {
    "total_calls": 10,
    "total_cost_cents": 5.2,
    "total_input_tokens": 5000,
    "total_output_tokens": 2000,
    "total_tokens": 7000
  },
  "budget_status": {
    "session_cost_cents": 5.2,
    "session_budget_cents": 50.0,
    "remaining_budget_cents": 44.8,
    "budget_used_percent": 10.4,
    "per_request_budget_cents": 5.0
  },
  "cost_per_operation": {
    "parser": 0.1,
    "helper": 0.3,
    "ai_assist": 1.0,
    "planning": 5.0,
    "full_agent": 5.0
  }
}
```

## Diagnostic Report Structure

Each LLM call generates a `DiagnosticReport` with:

```python
@dataclass
class DiagnosticReport:
    timestamp: str
    operation_type: str          # "parser", "helper", "planning", etc.
    model_used: str              # Actual model used
    model_expected: str          # Expected model
    model_validation: bool       # True if model matches expected
    
    has_tools_schema: bool       # True if tools were included
    tools_schema_size: int       # Size in bytes
    
    system_prompt_size: int      # Character count
    system_prompt_ok: bool       # True if within limits
    
    history_message_count: int   # Number of messages
    history_total_chars: int     # Total character count
    history_ok: bool             # True if within limits
    
    sheet_content_size: int      # Estimated sheet content size
    sheet_content_ok: bool       # True if within limits
    
    max_tokens_requested: int    # Requested max_tokens
    max_tokens_ok: bool          # True if appropriate for operation
    
    input_tokens: Optional[int]  # Actual input tokens from API
    output_tokens: Optional[int] # Actual output tokens from API
    estimated_cost: float        # Estimated cost in cents
    actual_cost: Optional[float] # Actual cost from API (if available)
    
    duration_ms: float           # Call duration in milliseconds
    
    is_spike: bool               # True if cost spike detected
    warnings: List[str]          # List of warning messages
    errors: List[str]            # List of error messages
```

## Alert System

The diagnostic alert system triggers when:

1. **Cost Spike Detected**: Cost exceeds 2x expected for operation type
2. **Validation Errors**: Pre-call validation fails
3. **Multiple Warnings**: 3+ warnings in a single call

Alerts are logged as warnings and can be extended to:
- Send webhooks
- Email notifications
- Push to monitoring systems

## Usage in Code

### Using Diagnostic Wrapper

```python
from sheetsmith.llm import LLMDiagnostics, DiagnosticAlertSystem
from sheetsmith.llm.diagnostic_wrapper import call_llm_with_diagnostics_sync

# Set up diagnostics
diagnostics = LLMDiagnostics(
    max_system_prompt_chars=500,
    max_history_messages=10,
)
alert_system = DiagnosticAlertSystem(enabled=True)

# Make LLM call with diagnostics
response, report = call_llm_with_diagnostics_sync(
    client=llm_client,
    messages=messages,
    system=system_prompt,
    tools=[],
    max_tokens=300,
    model="claude-3-haiku",
    operation_type="parser",
    expected_model="claude-3-haiku",
    diagnostics=diagnostics,
    alert_system=alert_system,
)

# Check report
if report.is_spike:
    print(f"Cost spike detected: {report.estimated_cost} cents")

if report.warnings:
    print(f"Warnings: {report.warnings}")
```

### Automatic Integration

The SheetSmith agent automatically integrates diagnostics for all LLM calls. No code changes required - just configure via environment variables.

## Log Format

All LLM calls produce structured JSON logs:

```json
{
  "timestamp": "2026-01-21T12:34:56Z",
  "operation": "parser",
  "model": "anthropic/claude-3.5-sonnet:free",
  "duration_ms": 245,
  "input_tokens": 150,
  "output_tokens": 50,
  "estimated_cost_usd": 0.001,
  "actual_cost_usd": 0.0009,
  "is_spike": false,
  "validation": {
    "model_ok": true,
    "tools_ok": true,
    "prompt_size_ok": true,
    "history_ok": true,
    "max_tokens_ok": true
  },
  "warnings": []
}
```

## Interpreting Diagnostic Reports

### Common Warnings

1. **"Tools schema present"**: Tools JSON was included. Consider using JSON mode instead for efficiency.

2. **"System prompt size exceeds threshold"**: System prompt is too large. Use minimal prompts for parser/helper operations.

3. **"Message history count exceeds threshold"**: Too many messages in history. Parser should be stateless, helpers should keep minimal context.

4. **"max_tokens is high for operation"**: max_tokens setting is higher than necessary for the operation type.

5. **"Model mismatch"**: Using a different model than configured/expected.

6. **"Cost spike detected"**: Actual cost significantly exceeds expected cost for operation type.

### Validation Checks

Each validation check indicates:
- ✅ **OK**: Within expected limits
- ⚠️ **Warning**: Outside normal range but not blocking
- ❌ **Error**: Critical issue that blocks the call

### Cost Spike Investigation

If a cost spike is detected:

1. Check `input_tokens` and `output_tokens` - are they higher than expected?
2. Review `model_used` - is an expensive model being used inappropriately?
3. Check `has_tools_schema` - are tools being included unnecessarily?
4. Review `history_message_count` - is too much context being sent?
5. Check `system_prompt_size` - is the system prompt too large?

## Best Practices

1. **Use Minimal Prompts**: Keep system prompts under 500 characters for parser/helper operations
2. **Limit History**: Parser should be stateless, helpers should keep 2-3 exchanges max
3. **Avoid Tools**: Use JSON mode instead of tools for better efficiency
4. **Right-Size Models**: Use Haiku for simple tasks, Sonnet for complex reasoning
5. **Monitor Regularly**: Check `/diagnostics/cost-summary` endpoint regularly
6. **Set Budgets**: Configure `PER_REQUEST_BUDGET_CENTS` and `SESSION_BUDGET_CENTS` appropriately
7. **Enable Alerts**: Set `ENABLE_COST_SPIKE_DETECTION=true` to catch anomalies early

## Troubleshooting

### High Costs for Parser Operations

Parser operations should cost ~0.1 cents. If higher:
- Check if full conversation history is being sent
- Verify minimal system prompt is being used
- Ensure no tools schema is included
- Check if appropriate model (Haiku) is being used

### False Positive Spike Alerts

If legitimate operations trigger spike alerts:
- Adjust `COST_SPIKE_THRESHOLD_MULTIPLIER` (default: 2.0)
- Review expected costs in `CostSpikeDetector.EXPECTED_COSTS`
- Check if operation type is correctly classified

### Missing Actual Cost Data

OpenRouter provides actual cost via `native_tokens_cost` field:
- Ensure `OPENROUTER_INCLUDE_USAGE=true`
- Check if model supports usage data
- Verify API response includes usage fields

## Future Enhancements

Potential future additions:
- Persistent database storage for long-term analysis
- Cost trend analysis and forecasting
- Anomaly detection using ML
- Integration with external monitoring (Datadog, Prometheus)
- Cost attribution by user/session
- Automated optimization recommendations
