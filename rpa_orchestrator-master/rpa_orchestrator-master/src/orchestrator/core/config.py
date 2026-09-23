from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RPA Orchestrator"
    app_env: str = "local"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    postgres_dsn: str = Field(default="postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
    seo_agent_dsn: str | None = None
    mongo_dsn: str = "mongodb://localhost:27017"
    mongo_database: str = "seo_flows"
    redis_dsn: str = "redis://localhost:6379/0"
    dashboard_user: str = ""
    dashboard_pass: str = ""
    bot_tokens: dict[str, str] = Field(default_factory=dict)
    post_monitor_ws_token: str = ""

    # Django backend used as the Instagram catalog proxy.
    instagram_backend_url: str = "http://10.0.0.90:8004"
    instagram_backend_token: str = ""

    bot_request_timeout_seconds: float = 30.0
    bot_max_retries: int = 3
    execution_lock_ttl_seconds: int = 900
    bot_presence_ttl_seconds: int = 60
    bot_heartbeat_grace_seconds: int = Field(default=60, ge=10)
    bot_reconciliation_interval_seconds: int = Field(default=15, ge=1)
    page_execution_log_ttl_seconds: int = 86400
    post_monitor_presence_ttl_seconds: int = Field(default=60, ge=10)
    post_monitor_max_message_bytes: int = Field(default=262_144, ge=1_024)

    brightlocal_api_key: str = ""
    brightlocal_api_base_url: str = "https://api.brightlocal.com"
    brightlocal_rank_num_results: int = Field(default=100, ge=1, le=100)
    brightlocal_rank_timeout_seconds: float = Field(default=45.0, gt=0)
    brightlocal_rank_poll_interval_seconds: float = Field(default=1.5, gt=0)

    rank_provider: Literal["serper", "brightlocal"] = "serper"
    serper_api_key: str = ""
    serper_api_base_url: str = "https://google.serper.dev"
    serper_rank_num_results: int = Field(default=100, ge=1, le=100)
    serper_request_timeout_seconds: float = Field(default=15.0, gt=0)

    @field_validator("seo_agent_dsn", mode="before")
    @classmethod
    def empty_seo_agent_dsn_is_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
