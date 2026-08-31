from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from app.return_engine.fee import FeeCalculator


PRICE_TICK = Decimal("0.001")


class TargetPriceCalculator:
    """Finds the lowest exchange tick whose estimated net return meets target."""

    def __init__(self, fee_calculator: FeeCalculator) -> None:
        self.fee_calculator = fee_calculator

    def calculate(
        self,
        *,
        remaining_cost: Decimal,
        remaining_quantity: int,
        target_return: Decimal,
    ) -> Decimal:
        self._validate_inputs(
            remaining_cost=remaining_cost,
            remaining_quantity=remaining_quantity,
            target_return=target_return,
        )
        quantity = Decimal(remaining_quantity)
        required_net = remaining_cost * (Decimal("1") + target_return)

        # Ignoring the nonnegative sell fee gives a useful lower bound. Grow the
        # upper bound until it satisfies the real fee-aware predicate, then binary
        # search integer ticks so no binary float or price rounding can enter.
        no_fee_price = required_net / quantity
        high = max(1, self._ceil_tick_index(no_fee_price))
        while not self._meets_target(
            tick_index=high,
            required_net=required_net,
            remaining_quantity=remaining_quantity,
        ):
            high *= 2

        low = 1
        while low < high:
            middle = (low + high) // 2
            if self._meets_target(
                tick_index=middle,
                required_net=required_net,
                remaining_quantity=remaining_quantity,
            ):
                high = middle
            else:
                low = middle + 1

        return Decimal(low) * PRICE_TICK

    def _meets_target(
        self,
        *,
        tick_index: int,
        required_net: Decimal,
        remaining_quantity: int,
    ) -> bool:
        price = Decimal(tick_index) * PRICE_TICK
        gross = price * Decimal(remaining_quantity)
        fee = self.fee_calculator.estimate_sell_fee(
            price=price,
            quantity=remaining_quantity,
        )
        return gross - fee >= required_net

    @staticmethod
    def _ceil_tick_index(price: Decimal) -> int:
        return int((price / PRICE_TICK).to_integral_value(rounding=ROUND_CEILING))

    @staticmethod
    def _validate_inputs(
        *,
        remaining_cost: Decimal,
        remaining_quantity: int,
        target_return: Decimal,
    ) -> None:
        for name, value in (
            ("remaining_cost", remaining_cost),
            ("target_return", target_return),
        ):
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be a Decimal")
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")
        if remaining_cost <= 0:
            raise ValueError("remaining_cost must be positive")
        if target_return < 0:
            raise ValueError("target_return must be nonnegative")
        if isinstance(remaining_quantity, bool) or not isinstance(remaining_quantity, int):
            raise TypeError("remaining_quantity must be an int")
        if remaining_quantity <= 0:
            raise ValueError("remaining_quantity must be positive")
