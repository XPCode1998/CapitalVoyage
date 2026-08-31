from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import SettlementMode


Symbol = Annotated[str, Field(min_length=1, max_length=32)]


class SecuritySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("symbol", check_fields=False)
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class SecurityCreate(SecuritySchema):
    symbol: Symbol
    name: Annotated[str, Field(min_length=1, max_length=120)]
    market: Annotated[str, Field(min_length=1, max_length=32)] = "CN"
    settlement_mode: SettlementMode = SettlementMode.T1
    trade_unit: Annotated[int, Field(gt=0)] = 100
    enabled: bool = True


class SecurityUpdate(SecuritySchema):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    market: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    settlement_mode: SettlementMode | None = None
    trade_unit: Annotated[int, Field(gt=0)] | None = None
    enabled: bool | None = None


class SecurityRead(SecuritySchema):
    symbol: str
    name: str
    market: str
    settlement_mode: SettlementMode
    trade_unit: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

