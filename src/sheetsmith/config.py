"""Configuration management for SheetSmith."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    """Application settings."""

    # Google Sheets API
    google_credentials_path: Path = Path(
        os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    )
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
    cors_allow_origins: list[str] = (
        os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") 
        if os.getenv("CORS_ALLOW_ORIGINS") else ["*"]
    )

    # Agent settings
    model_name: str = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))


settings = Settings()
