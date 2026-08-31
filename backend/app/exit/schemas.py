from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import ensure_aware


PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
PositiveQuantity = Annotated[int, Field(gt=0)]


class ExitSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExitAllocationInput(ExitSchema):
    voyage_id: int
    quantity: PositiveQuantity


class ExitCreate(ExitSchema):
    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    exit_time: datetime
    exit_price: PositiveDecimal
    total_quantity: PositiveQuantity
    total_fee: NonNegativeDecimal = Decimal("0")
    allocations: Annotated[list[ExitAllocationInput], Field(min_length=1)]

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exit_time")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class ExitAllocationRead(ExitSchema):
    id: int
    exit_transaction_id: int
    voyage_id: int
    quantity: int
    allocated_fee: Decimal
    realized_cost: Decimal
    realized_profit: Decimal
    realized_return: Decimal


class ExitRead(ExitSchema):
    id: int
    symbol: str
    exit_time: datetime
    exit_price: Decimal
    total_quantity: int
    total_fee: Decimal
    created_at: datetime
    allocations: list[ExitAllocationRead]

