from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exit.models import ExitAllocation, ExitTransaction


class ExitRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_transaction(self, transaction: ExitTransaction) -> ExitTransaction:
        self.session.add(transaction)
        return transaction

    def add_allocation(self, allocation: ExitAllocation) -> ExitAllocation:
        self.session.add(allocation)
        return allocation

    def get(self, transaction_id: int) -> ExitTransaction | None:
        return self.session.scalar(
            select(ExitTransaction)
            .where(ExitTransaction.id == transaction_id)
            .options(selectinload(ExitTransaction.allocations))
        )

    def list(self) -> list[ExitTransaction]:
        return list(
            self.session.scalars(
                select(ExitTransaction)
                .options(selectinload(ExitTransaction.allocations))
                .order_by(ExitTransaction.exit_time.desc(), ExitTransaction.id.desc())
            ).all()
        )

