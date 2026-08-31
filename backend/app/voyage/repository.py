from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.enums import VoyageStatus
from app.exit.models import ExitAllocation
from app.voyage.models import Voyage, VoyageSequence


class VoyageRepository:
    SEQUENCE_ID = 1

    def __init__(self, session: Session):
        self.session = session

    def get(self, voyage_id: int, *, with_allocations: bool = False) -> Voyage | None:
        statement = select(Voyage).where(Voyage.id == voyage_id)
        if with_allocations:
            statement = statement.options(selectinload(Voyage.exit_allocations))
            # An identity-map instance may already have an old allocations
            # collection. Always replace it with the database-backed truth.
            statement = statement.execution_options(populate_existing=True)
        return self.session.scalar(statement)

    def get_by_no(self, voyage_no: str) -> Voyage | None:
        return self.session.scalar(
            select(Voyage).where(Voyage.voyage_no == voyage_no.strip().upper())
        )

    def list(self, *, status: VoyageStatus | None = None) -> list[Voyage]:
        statement = (
            select(Voyage)
            .options(selectinload(Voyage.exit_allocations))
            .execution_options(populate_existing=True)
        )
        if status is not None:
            statement = statement.where(Voyage.status == status)
        return list(self.session.scalars(statement.order_by(Voyage.id)).all())

    def add(self, voyage: Voyage) -> Voyage:
        self.session.add(voyage)
        return voyage

    def has_open_for_slot(self, slot_id: int, *, excluding_id: int | None = None) -> bool:
        statement = select(Voyage.id).where(
            Voyage.slot_id == slot_id,
            Voyage.status == VoyageStatus.OPEN,
        )
        if excluding_id is not None:
            statement = statement.where(Voyage.id != excluding_id)
        return self.session.scalar(statement.limit(1)) is not None

    def allocated_quantity(self, voyage_id: int) -> int:
        value = self.session.scalar(
            select(func.coalesce(func.sum(ExitAllocation.quantity), 0)).where(
                ExitAllocation.voyage_id == voyage_id
            )
        )
        return int(value or 0)

    def remaining_quantity(self, voyage: Voyage | int) -> int:
        model = voyage if isinstance(voyage, Voyage) else self.get(voyage)
        if model is None:
            return 0
        return model.entry_quantity - self.allocated_quantity(model.id)

    def ensure_sequence(self) -> VoyageSequence:
        sequence = self.session.get(VoyageSequence, self.SEQUENCE_ID)
        if sequence is None:
            sequence = VoyageSequence(id=self.SEQUENCE_ID, next_value=1)
            self.session.add(sequence)
            self.session.flush()
        return sequence

    def acquire_ledger_write_lock(self) -> None:
        """Serialize ledger mutations using SQLite's single-writer lock.

        SQLite ignores SELECT FOR UPDATE. A no-op UPDATE on the persistent
        sequence row upgrades the transaction to a writer before any remaining
        quantity is read. Concurrent exits then wait and re-read fresh totals.
        """

        self.ensure_sequence()
        self.session.execute(
            update(VoyageSequence)
            .where(VoyageSequence.id == self.SEQUENCE_ID)
            .values(next_value=VoyageSequence.next_value)
        )

    def next_voyage_no(self) -> str:
        self.ensure_sequence()
        # One UPDATE statement acquires SQLite's write lock and returns the new
        # value, avoiding the read/modify/write race of MAX(voyage_no) + 1.
        next_value = self.session.scalar(
            update(VoyageSequence)
            .where(VoyageSequence.id == self.SEQUENCE_ID)
            .values(next_value=VoyageSequence.next_value + 1)
            .returning(VoyageSequence.next_value)
        )
        if next_value is None:  # defensive; ensure_sequence normally makes this impossible
            raise RuntimeError("voyage sequence is unavailable")
        allocated = int(next_value) - 1
        return f"QC-{allocated:04d}"
