from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import VoyageStatus
from app.core.time import ensure_aware


PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
PositiveQuantity = Annotated[int, Field(gt=0)]


class VoyageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VoyageCreate(VoyageSchema):
    slot_id: int
    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    entry_time: datetime
    entry_price: PositiveDecimal
    entry_quantity: PositiveQuantity
    entry_fee: NonNegativeDecimal = Decimal("0")
    target_return: PositiveDecimal = Decimal("0.02")
    sellable_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("entry_time", "sellable_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value) if value is not None else None


class VoyageUpdate(VoyageSchema):
    entry_time: datetime | None = None
    entry_price: PositiveDecimal | None = None
    entry_quantity: PositiveQuantity | None = None
    entry_fee: NonNegativeDecimal | None = None
    target_return: PositiveDecimal | None = None
    sellable_at: datetime | None = None

    @field_validator("entry_time", "sellable_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value) if value is not None else None


class VoyageRead(VoyageSchema):
    id: int
    voyage_no: str
    slot_id: int
    symbol: str
    entry_time: datetime
    entry_price: Decimal
    entry_quantity: int
    entry_fee: Decimal
    target_return: Decimal
    sellable_at: datetime
    status: VoyageStatus
    first_target_reached_at: datetime | None
    last_target_reached_at: datetime | None
    remaining_quantity: int
    created_at: datetime
    updated_at: datetime
