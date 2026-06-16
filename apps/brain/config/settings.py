from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    OPENAI_API_KEY: str = ""

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    WS_HOST: str = "0.0.0.0"
    WS_PORT: int = 8001

    APP_NAME: str = "RIRI"
    APP_VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()