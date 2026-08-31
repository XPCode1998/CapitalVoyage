from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        return log

    def list(self, *, limit: int = 100) -> list[AuditLog]:
        return list(
            self.session.scalars(
                select(AuditLog)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(max(1, min(limit, 1000)))
            ).all()
        )

