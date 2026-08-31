from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.audit.repository import AuditRepository
from app.core.enums import AuditAction


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def model_snapshot(model: Any) -> dict[str, Any]:
    """Serialize mapped columns only, excluding lazy relationships."""

    mapper = inspect(model).mapper
    return {
        attribute.key: _jsonable(getattr(model, attribute.key))
        for attribute in mapper.column_attrs
    }


class AuditService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = AuditRepository(session)

    def record(
        self,
        action: AuditAction,
        entity: str,
        entity_id: str | int,
        *,
        before: Mapping[str, Any] | None = None,
        after: Mapping[str, Any] | None = None,
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            before=self._dump(before),
            after=self._dump(after),
        )
        return self.repository.add(log)

    @staticmethod
    def _dump(value: Mapping[str, Any] | None) -> str | None:
        if value is None:
            return None
        return json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

