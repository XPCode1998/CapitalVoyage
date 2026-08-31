from __future__ import annotations

from dataclasses import fields
from decimal import Decimal

import pytest

from app.core.enums import RuntimeState
from app.return_engine import (
    FeeCalculator,
    FeeConfig,
    ReturnEngine,
    RuntimeResult,
    TargetPriceCalculator,
)


ZERO_FEE = FeeCalculator(FeeConfig())


def test_fee_calculator_uses_all_six_configurable_values() -> None:
    calculator = FeeCalculator(
        FeeConfig(
            buy_commission_rate=Decimal("0.001"),
            sell_commission_rate=Decimal("0.002"),
            minimum_buy_commission=Decimal("3"),
            minimum_sell_commission=Decimal("5"),
            other_buy_fee_rate=Decimal("0.0001"),
            other_sell_fee_rate=Decimal("0.0002"),
        )
    )

    assert calculator.estimate_buy_fee(price=Decimal("10"), quantity=1_000) == Decimal(
        "11"
    )
    assert calculator.estimate_sell_fee(price=Decimal("10"), quantity=1_000) == Decimal(
        "22"
    )


def test_fee_calculator_applies_minimum_commissions() -> None:
    calculator = FeeCalculator(
        FeeConfig(
            buy_commission_rate=Decimal("0.0003"),
            sell_commission_rate=Decimal("0.0002"),
            minimum_buy_commission=Decimal("5"),
            minimum_sell_commission=Decimal("6"),
        )
    )

    assert calculator.estimate_buy_fee(price=Decimal("1"), quantity=1_000) == Decimal(
        "5"
    )
    assert calculator.estimate_sell_fee(price=Decimal("1"), quantity=1_000) == Decimal(
        "6"
    )


def test_no_fee_two_percent_return_populates_every_runtime_field() -> None:
    result = ReturnEngine(ZERO_FEE).calculate(
        voyage_id=7,
        entry_price=Decimal("10"),
        entry_quantity=100,
        entry_fee=Decimal("0"),
        remaining_quantity=100,
        monitor_price=Decimal("10.2"),
        target_return=Decimal("0.02"),
        sellable=True,
    )

    assert {field.name for field in fields(RuntimeResult)} == {
        "voyage_id",
        "monitor_price",
        "price_return",
        "net_return",
        "target_return",
        "target_price",
        "distance_to_target",
        "remaining_quantity",
        "estimated_profit",
        "sellable",
        "runtime_state",
    }
    assert result.voyage_id == 7
    assert result.monitor_price == Decimal("10.2")
    assert result.price_return == Decimal("0.02")
    assert result.net_return == Decimal("0.02")
    assert result.target_return == Decimal("0.02")
    assert result.target_price.as_tuple().exponent == -3
    assert result.target_price == Decimal("10.200")
    assert result.distance_to_target == Decimal("0")
    assert result.remaining_quantity == 100
    assert result.estimated_profit == Decimal("20")
    assert result.sellable is True
    assert result.runtime_state == RuntimeState.READY_TO_RETURN


def test_one_percent_target_includes_entry_and_minimum_sell_fees() -> None:
    calculator = FeeCalculator(FeeConfig(minimum_sell_commission=Decimal("5")))
    result = ReturnEngine(calculator).calculate(
        voyage_id=1,
        entry_price=Decimal("10"),
        entry_quantity=100,
        entry_fee=Decimal("5"),
        remaining_quantity=100,
        monitor_price=Decimal("10.201"),
        target_return=Decimal("0.01"),
        sellable=True,
    )

    assert result.target_price == Decimal("10.201")
    assert result.net_return >= Decimal("0.01")
    assert result.runtime_state == RuntimeState.READY_TO_RETURN


def test_partial_remaining_quantity_uses_original_unit_cost() -> None:
    result = ReturnEngine(ZERO_FEE).calculate(
        voyage_id=9,
        entry_price=Decimal("10"),
        entry_quantity=1_000,
        entry_fee=Decimal("10"),
        remaining_quantity=400,
        monitor_price=Decimal("10.2"),
        target_return=Decimal("0.02"),
        sellable=True,
    )

    remaining_cost = Decimal("4004")
    assert result.estimated_profit == Decimal("4080") - remaining_cost
    assert result.net_return == Decimal("76") / remaining_cost
    assert result.target_price == Decimal("10.211")
    assert result.runtime_state == RuntimeState.NEAR_RETURN


@pytest.mark.parametrize(
    ("entry_price", "quantity", "target_return", "expected_target_price"),
    [
        (Decimal("4.012"), 12_500, Decimal("0.02"), Decimal("4.093")),
        (Decimal("1.237"), 100, Decimal("0.01"), Decimal("1.250")),
        (Decimal("23.456"), 7_900, Decimal("0.02"), Decimal("23.926")),
    ],
)
def test_target_price_supports_different_prices_quantities_and_targets(
    entry_price: Decimal,
    quantity: int,
    target_return: Decimal,
    expected_target_price: Decimal,
) -> None:
    remaining_cost = entry_price * Decimal(quantity)

    target_price = TargetPriceCalculator(ZERO_FEE).calculate(
        remaining_cost=remaining_cost,
        remaining_quantity=quantity,
        target_return=target_return,
    )

    assert target_price == expected_target_price


def test_target_price_is_lowest_fee_aware_tick_with_decimal_precision() -> None:
    calculator = FeeCalculator(
        FeeConfig(
            sell_commission_rate=Decimal("0.00037"),
            minimum_sell_commission=Decimal("5"),
            other_sell_fee_rate=Decimal("0.00002"),
        )
    )
    target = TargetPriceCalculator(calculator)
    remaining_cost = (
        Decimal("4.012345") * Decimal(12_800) + Decimal("5.123456")
    ) / Decimal(12_800) * Decimal(7_777)
    target_return = Decimal("0.02")

    target_price = target.calculate(
        remaining_cost=remaining_cost,
        remaining_quantity=7_777,
        target_return=target_return,
    )
    previous_price = target_price - Decimal("0.001")

    def estimated_return(price: Decimal) -> Decimal:
        proceeds = price * Decimal(7_777) - calculator.estimate_sell_fee(
            price=price,
            quantity=7_777,
        )
        return (proceeds - remaining_cost) / remaining_cost

    assert target_price.as_tuple().exponent == -3
    assert estimated_return(target_price) >= target_return
    assert estimated_return(previous_price) < target_return
    assert all(
        isinstance(value, Decimal)
        for value in (
            target_price,
            remaining_cost,
            estimated_return(target_price),
        )
    )


def test_runtime_state_distinguishes_near_and_not_sellable_target() -> None:
    engine = ReturnEngine(ZERO_FEE, near_return_buffer=Decimal("0.002"))
    near = engine.calculate(
        voyage_id=1,
        entry_price=Decimal("10"),
        entry_quantity=100,
        entry_fee=Decimal("0"),
        remaining_quantity=100,
        monitor_price=Decimal("10.18"),
        target_return=Decimal("0.02"),
        sellable=True,
    )
    reached_not_sellable = engine.calculate(
        voyage_id=2,
        entry_price=Decimal("10"),
        entry_quantity=100,
        entry_fee=Decimal("0"),
        remaining_quantity=100,
        monitor_price=Decimal("10.20"),
        target_return=Decimal("0.02"),
        sellable=False,
    )

    assert near.runtime_state == RuntimeState.NEAR_RETURN
    assert near.distance_to_target == Decimal("0.002")
    assert reached_not_sellable.runtime_state == RuntimeState.TARGET_REACHED_NOT_SELLABLE


def test_financial_inputs_reject_binary_float() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        ReturnEngine(ZERO_FEE).calculate(
            voyage_id=1,
            entry_price=10.0,  # type: ignore[arg-type]
            entry_quantity=100,
            entry_fee=Decimal("0"),
            remaining_quantity=100,
            monitor_price=Decimal("10.2"),
            target_return=Decimal("0.02"),
            sellable=True,
        )
