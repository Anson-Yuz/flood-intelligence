from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVER_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_URL = f"sqlite+pysqlite:///{(SERVER_DIR / 'yujian.db').as_posix()}"


class Settings(BaseSettings):
    app_name: str = "预鉴云边协同平台 API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = DEFAULT_SQLITE_URL
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )
    seed_demo_data: bool = True
    scenario_tick_seconds: float = 2.0
    event_stream_keepalive_seconds: float = 15.0
    api_prefix: str = "/api/v1"

    auth_cookie_name: str = "yujian_session"
    auth_cookie_samesite: str = "lax"
    auth_secure_cookie: bool = False
    auth_session_hours: int = Field(default=12, ge=1, le=168)
    auth_remember_days: int = Field(default=30, ge=1, le=365)
    auth_pbkdf2_iterations: int = Field(default=310_000, ge=100_000, le=2_000_000)
    auth_default_tenant_id: str = "demo-tenant"
    auth_seed_admin_username: str = "admin"
    auth_seed_admin_password: str | None = None
    auth_local_default_password: str = "Yujian@2026"
    auth_seed_admin_display_name: str = "王海峰"
    auth_seed_admin_role: str = "防汛值班长"

    model_config = SettingsConfigDict(
        env_file=SERVER_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("auth_cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax, strict, or none")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
