"""Application settings for the full-stack web app."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NeuroLearn"
    app_env: str = "development"

    secret_key: str = "dev-session-secret-change-me"
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    session_cookie_name: str = "neurolearn_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 7

    database_url: str = "sqlite:///./data/neurolearn.db"
    legacy_student_db_path: str = "./data/student_profiles.db"

    static_dir: str = "app/static"
    templates_dir: str = "app/templates"

    gemini_api_key: str = ""

    cors_origins_raw: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
