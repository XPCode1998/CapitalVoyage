from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.enums import AuditAction, VoyageStatus
from app.exit.models import ExitAllocation
from app.voyage.models import Voyage


class ReconcileService:
    def __init__(self, session: Session):
        self.session = session

    def reconcile(self, symbol: str, broker_quantity: int) -> dict:
        entry = self.session.scalar(select(func.coalesce(func.sum(Voyage.entry_quantity), 0)).where(Voyage.symbol == symbol, Voyage.status == VoyageStatus.OPEN)) or 0
        allocated = self.session.scalar(select(func.coalesce(func.sum(ExitAllocation.quantity), 0)).join(Voyage).where(Voyage.symbol == symbol, Voyage.status == VoyageStatus.OPEN)) or 0
        system_quantity = int(entry) - int(allocated)
        difference = broker_quantity - system_quantity
        result = {"symbol": symbol, "system_quantity": system_quantity, "broker_quantity": broker_quantity, "difference": difference, "matched": difference == 0}
        AuditService(self.session).record(AuditAction.RECONCILE_POSITION, "Security", symbol, after=result)
        self.session.commit()
        return result

