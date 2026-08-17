from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment
    variables and .env.
    """

    # ==================================================
    # OPENAI
    # ==================================================

    OPENAI_API_KEY: str = ""


    # ==================================================
    # FASTAPI
    # ==================================================

    API_HOST: str = "0.0.0.0"

    API_PORT: int = 8000


    # ==================================================
    # WEBSOCKET
    # ==================================================

    WS_HOST: str = "0.0.0.0"

    WS_PORT: int = 8001


    # ==================================================
    # APPLICATION
    # ==================================================

    APP_NAME: str = "RIRI"

    APP_VERSION: str = "0.1.0"


    # ==================================================
    # ENVIRONMENT
    # ==================================================

    ENVIRONMENT: str = "development"


    # ==================================================
    # CONFIGURATION
    # ==================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()