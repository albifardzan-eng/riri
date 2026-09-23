from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
_revision_file = BASE_DIR.parent.parent / "REVISION"
BUILD_REVISION = _revision_file.read_text().strip() if _revision_file.is_file() else "development"


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
    AI_EVENT_MIN_INTERVAL_SECONDS: int = Field(default=30, ge=10, le=3600)
    AI_PRICE_CHANGE_ATR: float = Field(default=0.25, gt=0)

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

    APP_VERSION: str = "1.4.0-part1"
    # Unsettled parameters are opt-in; no invented portfolio-risk cap.
    SMALL_EQUITY_STRICT: bool = True
    EXPERIMENTAL_SPREAD: bool = False
    MAX_SL_RISK_EQUITY_PERCENT: float | None = Field(default=None, gt=0, le=100)
    POSITION_REVIEW_ENABLED: bool = True
    POSITION_REVIEW_EXECUTE: bool = False
    POSITION_REVIEW_REPEAT_SECONDS: int = Field(default=900, ge=60)
    PRECLOSE_ENABLED: bool = False
    PRECLOSE_HOLD_MIN_CONFIDENCE: int | None = Field(default=None, ge=1, le=100)
    REVIEW_MAX_CALLS_PER_CYCLE: int = Field(default=1, ge=1, le=1)

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
