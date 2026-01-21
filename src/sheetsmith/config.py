"""Configuration management for SheetSmith."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


def _parse_cors_origins() -> list[str]:
    """Parse CORS origins from environment variable."""
    cors_env = os.getenv("CORS_ALLOW_ORIGINS")
    if cors_env:
        return cors_env.split(",")
    return ["*"]


class Settings(BaseModel):
    """Application settings."""

    # Google Sheets API credentials
    google_credentials_path: Path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
    google_token_path: Path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))

    # LLM Provider settings ('anthropic' or 'openrouter')
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")

    # Anthropic API key (required when LLM_PROVIDER=anthropic)
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # OpenRouter API configuration (required when LLM_PROVIDER=openrouter)
    openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

    # Database path for persistence
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/sheetsmith.db"))

    # Server settings
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS settings (comma-separated list of allowed origins, or * for all)
    cors_allow_origins: list[str] = _parse_cors_origins()

    # Agent settings - model configuration
    model_name: str = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Safety constraints - prevent expensive or dangerous operations
    max_cells_per_operation: int = int(os.getenv("MAX_CELLS_PER_OPERATION", "500"))
    max_sheets_per_operation: int = int(os.getenv("MAX_SHEETS_PER_OPERATION", "40"))
    max_formula_length: int = int(os.getenv("MAX_FORMULA_LENGTH", "50000"))
    require_preview_above_cells: int = int(os.getenv("REQUIRE_PREVIEW_ABOVE_CELLS", "10"))

    # Model selection by operation type (for cost optimization)
    planning_model: str = os.getenv("PLANNING_MODEL", "")  # Empty means use main model
    parser_model: str = os.getenv("PARSER_MODEL", "anthropic/claude-3-haiku")
    ai_assist_model: str = os.getenv("AI_ASSIST_MODEL", "anthropic/claude-3-haiku")
    
    # Token limits by operation type
    parser_max_tokens: int = int(os.getenv("PARSER_MAX_TOKENS", "300"))
    ai_assist_max_tokens: int = int(os.getenv("AI_ASSIST_MAX_TOKENS", "400"))
    planning_max_tokens: int = int(os.getenv("PLANNING_MAX_TOKENS", "800"))
    
    # Hard caps for payload size
    prompt_max_chars: int = int(os.getenv("PROMPT_MAX_CHARS", "10000"))
    spreadsheet_content_max_chars: int = int(os.getenv("SPREADSHEET_CONTENT_MAX_CHARS", "5000"))
    formula_sample_limit: int = int(os.getenv("FORMULA_SAMPLE_LIMIT", "5"))
    
    # Cost Optimization Settings
    use_json_mode: bool = os.getenv("USE_JSON_MODE", "true").lower() == "true"  # Enable JSON-only mode (no tool schemas sent to LLM)
    use_free_models: bool = os.getenv("USE_FREE_MODELS", "false").lower() == "true"  # Use free models when available (adds :free suffix to OpenRouter models)

    # Cost Tracking and Logging
    enable_cost_logging: bool = os.getenv("ENABLE_COST_LOGGING", "true").lower() == "true"  # Log LLM API costs to file
    cost_log_path: Path = Path(os.getenv("COST_LOG_PATH", "logs/llm_costs.jsonl"))  # Path to cost log file
    
    # Budget Guards - prevent runaway costs
    payload_max_chars: int = int(os.getenv("PAYLOAD_MAX_CHARS", "50000"))  # Maximum characters in a single request payload
    max_input_tokens: int = int(os.getenv("MAX_INPUT_TOKENS", "100000"))  # Maximum input tokens per request
    per_request_budget_cents: float = float(os.getenv("PER_REQUEST_BUDGET_CENTS", "5.0"))  # Maximum cost per individual request
    session_budget_cents: float = float(os.getenv("SESSION_BUDGET_CENTS", "50.0"))  # Maximum total cost per session
    alert_on_high_cost: bool = os.getenv("ALERT_ON_HIGH_COST", "true").lower() == "true"  # Alert when request exceeds high cost threshold
    high_cost_threshold_cents: float = float(os.getenv("HIGH_COST_THRESHOLD_CENTS", "1.0"))  # Cost threshold for alerts

    # Safety and preview settings
    preview_ttl_seconds: int = int(os.getenv("PREVIEW_TTL_SECONDS", "300"))  # 5 minutes
    enable_dry_run: bool = os.getenv("ENABLE_DRY_RUN", "true").lower() == "true"
    auto_audit_on_connect: bool = os.getenv("AUTO_AUDIT_ON_CONNECT", "true").lower() == "true"
    max_preview_diffs_displayed: int = int(os.getenv("MAX_PREVIEW_DIFFS_DISPLAYED", "100"))

    # Diagnostics - monitoring and alerting thresholds
    enable_cost_spike_detection: bool = os.getenv("ENABLE_COST_SPIKE_DETECTION", "true").lower() == "true"  # Detect unusual cost spikes
    max_system_prompt_chars: int = int(os.getenv("MAX_SYSTEM_PROMPT_CHARS", "5000"))  # Maximum system prompt size
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "10"))  # Maximum conversation history messages
    max_sheet_content_chars: int = int(os.getenv("MAX_SHEET_CONTENT_CHARS", "5000"))  # Maximum spreadsheet content size
    max_tools_schema_bytes: int = int(os.getenv("MAX_TOOLS_SCHEMA_BYTES", "50000"))  # Maximum tool schema size in bytes
    cost_spike_threshold_multiplier: float = float(os.getenv("COST_SPIKE_THRESHOLD_MULTIPLIER", "3.0"))  # Multiplier for cost spike detection

    # OpenRouter usage tracking
    openrouter_include_usage: bool = os.getenv("OPENROUTER_INCLUDE_USAGE", "true").lower() == "true"


settings = Settings()
