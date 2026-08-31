from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RuntimeState


class ReturnCenterSchema(BaseModel):
    model_config = ConfigDict(frozen=True)


class ReadyVoyage(ReturnCenterSchema):
    voyage_no: str
    remaining_quantity: int = Field(gt=0)
    entry_price: Decimal
    monitor_price: Decimal
    net_return: Decimal
    target_return: Decimal
    runtime_state: RuntimeState


class ReturnGroup(ReturnCenterSchema):
    symbol: str
    name: str
    system_total_quantity: int = Field(gt=0)
    ready_quantity: int = Field(gt=0)
    ready_voyages: list[ReadyVoyage]

