from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum as SAEnum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuditAction
from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(
            AuditAction,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="audit_action",
        ),
        nullable=False,
        index=True,
    )
    entity: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    before: Mapped[str | None] = mapped_column(Text)
    after: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, nullable=False, index=True
    )

