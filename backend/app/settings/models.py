from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime, DecimalType


class AppSettings(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("slot_count > 0", name="ck_settings_slot_count"),
        CheckConstraint("market_poll_interval_seconds >= 5", name="ck_settings_poll"),
        CheckConstraint("market_quote_stale_seconds > 0", name="ck_settings_stale"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    total_capital: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    slot_count: Mapped[int] = mapped_column(nullable=False)
    default_slot_amount: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    default_target_return: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    near_return_buffer: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    long_voyage_days: Mapped[int] = mapped_column(nullable=False)
    market_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    market_poll_interval_seconds: Mapped[int] = mapped_column(nullable=False)
    market_quote_stale_seconds: Mapped[int] = mapped_column(nullable=False)
    return_price_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    buy_commission_rate: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("0.0003"), nullable=False)
    sell_commission_rate: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("0.0003"), nullable=False)
    minimum_buy_commission: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("5"), nullable=False)
    minimum_sell_commission: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("5"), nullable=False)
    other_buy_fee_rate: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("0"), nullable=False)
    other_sell_fee_rate: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("0"), nullable=False)
    notification_provider: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    notification_webhook_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    alert_cooldown_minutes: Mapped[int] = mapped_column(default=30, nullable=False)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=now_shanghai, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False)

