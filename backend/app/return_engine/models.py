from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal

from app.core.enums import RuntimeState


def _validate_nonnegative_decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


@dataclass(frozen=True, slots=True)
class FeeConfig:
    """All configurable fee components used by buy and sell estimates."""

    buy_commission_rate: Decimal = Decimal("0")
    sell_commission_rate: Decimal = Decimal("0")
    minimum_buy_commission: Decimal = Decimal("0")
    minimum_sell_commission: Decimal = Decimal("0")
    other_buy_fee_rate: Decimal = Decimal("0")
    other_sell_fee_rate: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for field in fields(self):
            _validate_nonnegative_decimal(field.name, getattr(self, field.name))

        if self.buy_commission_rate + self.other_buy_fee_rate >= 1:
            raise ValueError("aggregate buy fee rate must be less than one")
        if self.sell_commission_rate + self.other_sell_fee_rate >= 1:
            raise ValueError("aggregate sell fee rate must be less than one")


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    voyage_id: int
    monitor_price: Decimal
    price_return: Decimal
    net_return: Decimal
    target_return: Decimal
    target_price: Decimal
    distance_to_target: Decimal
    remaining_quantity: int
    estimated_profit: Decimal
    sellable: bool
    runtime_state: RuntimeState
