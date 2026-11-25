"""Runtime configuration (env-driven). Demo mode is the safe default for public deployments."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{REPO_ROOT / 'ars.db'}"
    demo_mode: bool = Field(default=True, description="Read-only public demo: mutations are rejected.")
    admin_token: str = Field(default="", description="Required (X-Admin-Token) for mutations when demo_mode=false.")
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    enable_coding_execution: bool = False  # local/admin only; never enabled from the public web
    log_level: str = "INFO"
    # SAFE default: error details are hidden unless ENVIRONMENT=development is set explicitly (scripts/dev.sh does).
    environment: str = "production"
    max_body_bytes: int = 65_536
    admin_fail_limit_per_minute: int = 10
    calibrate_max_seconds: float = 30.0
    calibrate_max_items: int = 1000
    otlp_endpoint: str = ""  # e.g. http://localhost:6006/v1/traces (Phoenix); empty = disabled
    stale_job_seconds: int = 120
    live_rate_limit_per_minute: int = 6
    # Only these peers may set X-Forwarded-For (the web service / load balancer). Never "*" on a public API.
    forwarded_allow_ips: str = "127.0.0.1"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
