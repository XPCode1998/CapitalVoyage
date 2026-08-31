from __future__ import annotations

from decimal import Decimal

from app.core.enums import RuntimeState
from app.return_engine.fee import FeeCalculator
from app.return_engine.models import RuntimeResult
from app.return_engine.target import TargetPriceCalculator


class ReturnEngine:
    """Calculates fee-aware runtime returns for one open Voyage."""

    def __init__(
        self,
        fee_calculator: FeeCalculator | None = None,
        *,
        near_return_buffer: Decimal = Decimal("0.002"),
    ) -> None:
        if not isinstance(near_return_buffer, Decimal):
            raise TypeError("near_return_buffer must be a Decimal")
        if not near_return_buffer.is_finite() or near_return_buffer < 0:
            raise ValueError("near_return_buffer must be finite and nonnegative")
        self.fee_calculator = fee_calculator or FeeCalculator()
        self.target_price_calculator = TargetPriceCalculator(self.fee_calculator)
        self.near_return_buffer = near_return_buffer

    def calculate(
        self,
        *,
        voyage_id: int,
        entry_price: Decimal,
        entry_quantity: int,
        entry_fee: Decimal,
        remaining_quantity: int,
        monitor_price: Decimal,
        target_return: Decimal,
        sellable: bool,
    ) -> RuntimeResult:
        self._validate_inputs(
            voyage_id=voyage_id,
            entry_price=entry_price,
            entry_quantity=entry_quantity,
            entry_fee=entry_fee,
            remaining_quantity=remaining_quantity,
            monitor_price=monitor_price,
            target_return=target_return,
            sellable=sellable,
        )

        entry_quantity_decimal = Decimal(entry_quantity)
        remaining_quantity_decimal = Decimal(remaining_quantity)
        entry_cost = entry_price * entry_quantity_decimal + entry_fee
        unit_cost = entry_cost / entry_quantity_decimal
        remaining_cost = unit_cost * remaining_quantity_decimal

        estimated_gross = monitor_price * remaining_quantity_decimal
        estimated_exit_fee = self.fee_calculator.estimate_sell_fee(
            price=monitor_price,
            quantity=remaining_quantity,
        )
        estimated_net = estimated_gross - estimated_exit_fee
        estimated_profit = estimated_net - remaining_cost
        net_return = estimated_profit / remaining_cost
        price_return = (monitor_price - entry_price) / entry_price

        target_price = self.target_price_calculator.calculate(
            remaining_cost=remaining_cost,
            remaining_quantity=remaining_quantity,
            target_return=target_return,
        )
        distance_to_target = max(target_return - net_return, Decimal("0"))
        runtime_state = self._runtime_state(
            net_return=net_return,
            target_return=target_return,
            sellable=sellable,
        )

        return RuntimeResult(
            voyage_id=voyage_id,
            monitor_price=monitor_price,
            price_return=price_return,
            net_return=net_return,
            target_return=target_return,
            target_price=target_price,
            distance_to_target=distance_to_target,
            remaining_quantity=remaining_quantity,
            estimated_profit=estimated_profit,
            sellable=sellable,
            runtime_state=runtime_state,
        )

    def _runtime_state(
        self,
        *,
        net_return: Decimal,
        target_return: Decimal,
        sellable: bool,
    ) -> RuntimeState:
        if net_return >= target_return:
            if sellable:
                return RuntimeState.READY_TO_RETURN
            return RuntimeState.TARGET_REACHED_NOT_SELLABLE
        if net_return >= target_return - self.near_return_buffer:
            return RuntimeState.NEAR_RETURN
        return RuntimeState.IN_FLIGHT

    @staticmethod
    def _validate_inputs(
        *,
        voyage_id: int,
        entry_price: Decimal,
        entry_quantity: int,
        entry_fee: Decimal,
        remaining_quantity: int,
        monitor_price: Decimal,
        target_return: Decimal,
        sellable: bool,
    ) -> None:
        if isinstance(voyage_id, bool) or not isinstance(voyage_id, int):
            raise TypeError("voyage_id must be an int")
        if voyage_id <= 0:
            raise ValueError("voyage_id must be positive")

        for name, value in (
            ("entry_price", entry_price),
            ("entry_fee", entry_fee),
            ("monitor_price", monitor_price),
            ("target_return", target_return),
        ):
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be a Decimal")
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")

        if entry_price <= 0:
            raise ValueError("entry_price must be positive")
        if entry_fee < 0:
            raise ValueError("entry_fee must be nonnegative")
        if monitor_price <= 0:
            raise ValueError("monitor_price must be positive")
        if target_return < 0:
            raise ValueError("target_return must be nonnegative")

        for name, value in (
            ("entry_quantity", entry_quantity),
            ("remaining_quantity", remaining_quantity),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if remaining_quantity > entry_quantity:
            raise ValueError("remaining_quantity cannot exceed entry_quantity")
        if not isinstance(sellable, bool):
            raise TypeError("sellable must be a bool")
