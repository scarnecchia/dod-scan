"""Configuration loaded from environment variables and .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_model: str = "anthropic/claude-haiku-4-5-20251001"
    mapbox_token: str = ""
    database_path: Path = Path("./dod_scan.db")
    output_dir: Path = Path("./output")
    log_dir: Path = Path("./logs")


def get_settings() -> Settings:
    return Settings()
