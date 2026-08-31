from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CapitalVoyage"
    app_env: str = "development"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'capital_voyage.db'}"
    timezone: str = "Asia/Shanghai"

    market_provider: str = "akshare"
    market_poll_interval_seconds: int = Field(default=15, ge=5)
    market_quote_stale_seconds: int = Field(default=30, ge=1)

    default_capital: str = "500000"
    default_slot_count: int = Field(default=10, ge=1, le=100)
    default_slot_amount: str = "50000"
    default_target_return: str = "0.02"
    near_return_buffer: str = "0.002"
    long_voyage_days: int = Field(default=10, ge=1)
    return_price_mode: str = "BID1"

    buy_commission_rate: str = "0.0003"
    sell_commission_rate: str = "0.0003"
    minimum_buy_commission: str = "5"
    minimum_sell_commission: str = "5"
    other_buy_fee_rate: str = "0"
    other_sell_fee_rate: str = "0"

    notification_provider: str = "none"
    notification_webhook_url: str = ""
    alert_cooldown_minutes: int = Field(default=30, ge=0)
    scheduler_enabled: bool = True

    @property
    def resolved_database_url(self) -> str:
        prefixes = ("sqlite:///", "sqlite+pysqlite:///")
        prefix = next(
            (candidate for candidate in prefixes if self.database_url.startswith(candidate)),
            None,
        )
        if prefix is None:
            return self.database_url
        raw_path = self.database_url[len(prefix) :]

        # SQLite's in-memory and URI-style databases are not filesystem paths.
        if raw_path == ":memory:" or raw_path.startswith("file:"):
            return self.database_url

        path_text, separator, query = raw_path.partition("?")
        path = Path(path_text).expanduser()
        if path.is_absolute():
            return self.database_url
        # The documented URL is relative to backend/, independent of process cwd.
        resolved_path = (PROJECT_ROOT / "backend" / path).resolve()
        suffix = f"{separator}{query}" if separator else ""
        return f"{prefix}{resolved_path}{suffix}"


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
