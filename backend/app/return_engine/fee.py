from __future__ import annotations

from decimal import Decimal

from app.return_engine.models import FeeConfig


class FeeCalculator:
    """Estimates fees without introducing float or hidden fixed parameters."""

    def __init__(self, config: FeeConfig | None = None) -> None:
        self.config = config or FeeConfig()

    def estimate_buy_fee(self, *, price: Decimal, quantity: int) -> Decimal:
        return self._estimate(
            price=price,
            quantity=quantity,
            commission_rate=self.config.buy_commission_rate,
            minimum_commission=self.config.minimum_buy_commission,
            other_fee_rate=self.config.other_buy_fee_rate,
        )

    def estimate_sell_fee(self, *, price: Decimal, quantity: int) -> Decimal:
        return self._estimate(
            price=price,
            quantity=quantity,
            commission_rate=self.config.sell_commission_rate,
            minimum_commission=self.config.minimum_sell_commission,
            other_fee_rate=self.config.other_sell_fee_rate,
        )

    @staticmethod
    def _estimate(
        *,
        price: Decimal,
        quantity: int,
        commission_rate: Decimal,
        minimum_commission: Decimal,
        other_fee_rate: Decimal,
    ) -> Decimal:
        if not isinstance(price, Decimal):
            raise TypeError("price must be a Decimal")
        if not price.is_finite() or price <= 0:
            raise ValueError("price must be finite and positive")
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise TypeError("quantity must be an int")
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        gross = price * Decimal(quantity)
        commission = max(gross * commission_rate, minimum_commission)
        return commission + gross * other_fee_rate
