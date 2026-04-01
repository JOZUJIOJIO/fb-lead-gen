"""Application configuration loaded from environment variables."""

import secrets
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ADMIN_PASSWORD: str = "admin123456"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://leadflow:leadflow123@postgres:5432/leadflow"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # AI Provider: openai | anthropic | kimi | openrouter
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    KIMI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None

    # Browser proxy
    PROXY_SERVER: Optional[str] = None

    # Message sending limits
    SEND_INTERVAL_MIN: int = 60
    SEND_INTERVAL_MAX: int = 180
    MAX_DAILY_MESSAGES: int = 50

    # Auto-reply
    AUTO_REPLY_ENABLED: bool = True
    AUTO_REPLY_INTERVAL: int = 3600  # seconds between checks
    AUTO_REPLY_MAX_ROUNDS: int = 10

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
