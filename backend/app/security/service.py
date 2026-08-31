from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.time import now_shanghai
from app.security.models import Security
from app.security.repository import SecurityRepository
from app.security.schemas import SecurityCreate, SecurityUpdate


class SecurityService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = SecurityRepository(session)

    def create(self, payload: SecurityCreate) -> Security:
        if self.repository.get(payload.symbol) is not None:
            raise DomainError("SECURITY_EXISTS", "证券已存在", 409)
        security = Security(**payload.model_dump())
        self.repository.add(security)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise DomainError("SECURITY_EXISTS", "证券已存在", 409) from exc
        self.session.refresh(security)
        return security

    def get(self, symbol: str) -> Security:
        security = self.repository.get(symbol)
        if security is None:
            raise DomainError("SECURITY_NOT_FOUND", "证券不存在", 404)
        return security

    def update(self, symbol: str, payload: SecurityUpdate) -> Security:
        security = self.get(symbol)
        for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(security, field, value)
        security.updated_at = now_shanghai()
        self.session.commit()
        self.session.refresh(security)
        return security

    def search(self, query: str, *, limit: int = 20) -> list[Security]:
        return self.repository.search(query, limit=limit)

