from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_capital: Decimal | None = Field(default=None, gt=0)
    slot_count: int | None = Field(default=None, ge=1, le=100)
    default_slot_amount: Decimal | None = Field(default=None, gt=0)
    default_target_return: Decimal | None = Field(default=None, gt=0)
    near_return_buffer: Decimal | None = Field(default=None, ge=0)
    long_voyage_days: int | None = Field(default=None, ge=1)
    market_provider: str | None = None
    market_poll_interval_seconds: int | None = Field(default=None, ge=5)
    market_quote_stale_seconds: int | None = Field(default=None, ge=1)
    return_price_mode: str | None = None
    buy_commission_rate: Decimal | None = Field(default=None, ge=0)
    sell_commission_rate: Decimal | None = Field(default=None, ge=0)
    minimum_buy_commission: Decimal | None = Field(default=None, ge=0)
    minimum_sell_commission: Decimal | None = Field(default=None, ge=0)
    other_buy_fee_rate: Decimal | None = Field(default=None, ge=0)
    other_sell_fee_rate: Decimal | None = Field(default=None, ge=0)
    notification_provider: str | None = None
    notification_webhook_url: str | None = None
    alert_cooldown_minutes: int | None = Field(default=None, ge=0)
