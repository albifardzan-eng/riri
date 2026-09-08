from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """
    Application configuration loaded from environment
    variables and .env.
    """

    # ==================================================
    # OPENAI
    # ==================================================

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5-mini"
    OPENAI_TIMEOUT_SECONDS: float = 20.0
    # Responses API counts both visible JSON and internal reasoning tokens.
    # Keep this configurable so a reasoning model is not truncated before it
    # can emit the small structured decision payload.
    OPENAI_MAX_OUTPUT_TOKENS: int = Field(default=2048, ge=256, le=8192)
    AI_MIN_CALL_INTERVAL_SECONDS: int = Field(default=60, ge=10, le=3600)

    # Shared secrets are intentionally required at runtime and must never be
    # committed. MT5 uses RIRI_MT5_API_KEY; the server-rendered dashboard uses
    # a separate read-only credential.
    RIRI_MT5_API_KEY: str = ""
    RIRI_DASHBOARD_API_KEY: str = ""


    # ==================================================
    # FASTAPI
    # ==================================================

    API_HOST: str = "0.0.0.0"

    API_PORT: int = 8000


    # ==================================================
    # APPLICATION
    # ==================================================

    APP_NAME: str = "RIRI"

    APP_VERSION: str = "1.1.4"

    SIGNAL_EXPIRY_SECONDS: int = 60
    SIGNAL_DELIVERY_LEASE_SECONDS: int = 15
    MAX_MARKET_AGE_SECONDS: int = 30
    MIN_MARKET_INTERVAL_SECONDS: int = 5
    RIRI_STATE_DIR: str = str(BASE_DIR / "data")


    # ==================================================
    # ENVIRONMENT
    # ==================================================

    ENVIRONMENT: str = "development"


    # ==================================================
    # CONFIGURATION
    # ==================================================

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
