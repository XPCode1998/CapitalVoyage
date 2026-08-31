from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.enums import ReturnPriceMode


def _validate_price(name: str, value: Decimal | None, *, positive: bool) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal or None")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    if not positive and value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _validate_aware(name: str, value: datetime) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    name: str
    last_price: Decimal
    bid1: Decimal | None
    ask1: Decimal | None
    quote_time: datetime
    received_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        _validate_price("last_price", self.last_price, positive=True)
        _validate_price("bid1", self.bid1, positive=False)
        _validate_price("ask1", self.ask1, positive=False)
        _validate_aware("quote_time", self.quote_time)
        _validate_aware("received_at", self.received_at)

    @property
    def monitor_price(self) -> Decimal:
        """Default conservative price: positive BID1, falling back to LAST."""

        return self.price_for(ReturnPriceMode.BID1)

    def price_for(self, mode: ReturnPriceMode | str) -> Decimal:
        selected_mode = ReturnPriceMode(mode)
        if selected_mode == ReturnPriceMode.LAST:
            return self.last_price
        if self.bid1 is not None and self.bid1 > 0:
            return self.bid1
        return self.last_price
