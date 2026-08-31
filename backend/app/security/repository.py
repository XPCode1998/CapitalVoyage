from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.security.models import Security


class SecurityRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, symbol: str) -> Security | None:
        return self.session.get(Security, symbol.strip().upper())

    def add(self, security: Security) -> Security:
        self.session.add(security)
        return security

    def list(self, *, enabled_only: bool = False) -> list[Security]:
        statement = select(Security)
        if enabled_only:
            statement = statement.where(Security.enabled.is_(True))
        return list(self.session.scalars(statement.order_by(Security.symbol)).all())

    def search(self, query: str, *, limit: int = 20) -> list[Security]:
        normalized = query.strip().lower()
        statement = select(Security).where(Security.enabled.is_(True))
        if normalized:
            pattern = f"%{normalized}%"
            statement = statement.where(
                or_(
                    func.lower(Security.symbol).like(pattern),
                    func.lower(Security.name).like(pattern),
                )
            )
        return list(
            self.session.scalars(
                statement.order_by(Security.symbol).limit(max(1, min(limit, 100)))
            ).all()
        )

