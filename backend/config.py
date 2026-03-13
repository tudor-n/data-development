"""
App configuration — reads from environment variables with sane defaults.
No crash if values are missing; LLM features degrade gracefully.
"""
import os
import secrets
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown env vars — don't crash
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./clarifi_dev.db"

    # JWT
    secret_key: str = secrets.token_urlsafe(32)  # override in production!
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # CORS — accepts comma-separated string or Python list
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> str:
        if isinstance(v, list):
            return ",".join(v)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Gemini LLM — optional; features degrade without it
    gemini_api_key: str | None = None

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    # Upload limits
    max_file_size_mb: int = 10
    max_rows_for_analysis: int = 50_000

    # Cookies
    cookie_secure: bool = True  # set to False for local HTTP dev

    # Environment
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
