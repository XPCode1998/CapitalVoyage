from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import SlotStatus


PositiveDecimal = Annotated[Decimal, Field(gt=0)]


class CapitalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CapitalPoolRead(CapitalSchema):
    id: int
    name: str
    total_capital: Decimal
    default_target_return: Decimal
    created_at: datetime
    updated_at: datetime


class CapitalPoolUpdate(CapitalSchema):
    total_capital: PositiveDecimal | None = None
    default_target_return: PositiveDecimal | None = None


class CapitalSlotRead(CapitalSchema):
    id: int
    slot_no: int
    budget_amount: Decimal
    status: SlotStatus
    created_at: datetime
    updated_at: datetime

