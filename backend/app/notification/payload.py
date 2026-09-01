from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AlertNotification:
    """Presentation-ready alert data shared by every notification channel."""

    event_type: str
    message: str
    voyage_no: str
    symbol: str
    security_name: str
    slot_no: int
    net_return: Decimal
    target_return: Decimal
    distance_to_target: Decimal
    monitor_price: Decimal
    target_price: Decimal
    remaining_quantity: int
    quote_time: datetime | None
    interval_minutes: int
