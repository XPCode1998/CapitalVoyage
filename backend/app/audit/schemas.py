from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.enums import AuditAction


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: AuditAction
    entity: str
    entity_id: str
    before: str | None
    after: str | None
    created_at: datetime


class AuditRecord(BaseModel):
    action: AuditAction
    entity: str
    entity_id: str | int
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

