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

    # Google Sheets API
    google_credentials_path: Path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
    google_token_path: Path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))

    # LLM Provider settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")

    # Anthropic API
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # OpenRouter API
    openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

    # Database
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/sheetsmith.db"))

    # Server
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS settings
    cors_allow_origins: list[str] = _parse_cors_origins()

    # Agent settings
    model_name: str = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Safety constraints
    max_cells_per_operation: int = int(os.getenv("MAX_CELLS_PER_OPERATION", "500"))
    max_sheets_per_operation: int = int(os.getenv("MAX_SHEETS_PER_OPERATION", "40"))
    max_formula_length: int = int(os.getenv("MAX_FORMULA_LENGTH", "50000"))
    require_preview_above_cells: int = int(os.getenv("REQUIRE_PREVIEW_ABOVE_CELLS", "10"))

    # Model selection for different operations
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
    
    # Operation mode settings
    use_json_mode: bool = os.getenv("USE_JSON_MODE", "true").lower() == "true"  # Use JSON-only instead of tools
    use_free_models: bool = os.getenv("USE_FREE_MODELS", "false").lower() == "true"  # Use :free suffix

    # Cost tracking and limits
    enable_cost_logging: bool = os.getenv("ENABLE_COST_LOGGING", "true").lower() == "true"
    cost_log_path: Path = Path(os.getenv("COST_LOG_PATH", "logs/llm_costs.jsonl"))
    payload_max_chars: int = int(os.getenv("PAYLOAD_MAX_CHARS", "50000"))
    max_input_tokens: int = int(os.getenv("MAX_INPUT_TOKENS", "100000"))
    per_request_budget_cents: float = float(os.getenv("PER_REQUEST_BUDGET_CENTS", "5.0"))
    session_budget_cents: float = float(os.getenv("SESSION_BUDGET_CENTS", "50.0"))
    alert_on_high_cost: bool = os.getenv("ALERT_ON_HIGH_COST", "true").lower() == "true"
    high_cost_threshold_cents: float = float(os.getenv("HIGH_COST_THRESHOLD_CENTS", "1.0"))

    # Safety and preview settings
    preview_ttl_seconds: int = int(os.getenv("PREVIEW_TTL_SECONDS", "300"))  # 5 minutes
    enable_dry_run: bool = os.getenv("ENABLE_DRY_RUN", "true").lower() == "true"
    auto_audit_on_connect: bool = os.getenv("AUTO_AUDIT_ON_CONNECT", "true").lower() == "true"
    max_preview_diffs_displayed: int = int(os.getenv("MAX_PREVIEW_DIFFS_DISPLAYED", "100"))

    # Diagnostic thresholds
    max_system_prompt_chars: int = int(os.getenv("MAX_SYSTEM_PROMPT_CHARS", "500"))
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "10"))
    max_sheet_content_chars: int = int(os.getenv("MAX_SHEET_CONTENT_CHARS", "5000"))
    max_tools_schema_bytes: int = int(os.getenv("MAX_TOOLS_SCHEMA_BYTES", "0"))

    # Cost spike detection
    enable_cost_spike_detection: bool = os.getenv("ENABLE_COST_SPIKE_DETECTION", "true").lower() == "true"
    cost_spike_threshold_multiplier: float = float(os.getenv("COST_SPIKE_THRESHOLD_MULTIPLIER", "2.0"))

    # OpenRouter usage tracking
    openrouter_include_usage: bool = os.getenv("OPENROUTER_INCLUDE_USAGE", "true").lower() == "true"


settings = Settings()
