from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return serialize(value.model_dump())
    if is_dataclass(value):
        return serialize(asdict(value))
    inspected = sa_inspect(value, raiseerr=False)
    if inspected is not None and hasattr(inspected, "mapper"):
        return {attribute.key: serialize(getattr(value, attribute.key)) for attribute in inspected.mapper.column_attrs}
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize(v) for v in value]
    return value


def success(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": serialize(data), "error": None})


def failure(code: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": None, "error": {"code": code, "message": message}})
