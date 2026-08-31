from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext


getcontext().prec = 28

ZERO = Decimal("0")
MONEY_QUANT = Decimal("0.01")
PRICE_QUANT = Decimal("0.000001")
RATE_QUANT = Decimal("0.00000001")
FEE_QUANT = Decimal("0.01")


def as_decimal(value: Decimal | str | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantize_fee(value: Decimal) -> Decimal:
    return value.quantize(FEE_QUANT, rounding=ROUND_HALF_UP)


def decimal_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")

