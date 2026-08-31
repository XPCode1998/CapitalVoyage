from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capital.models import CapitalPool, CapitalSlot
from app.core.enums import SlotStatus


class CapitalPoolRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self) -> CapitalPool | None:
        return self.session.scalar(select(CapitalPool).order_by(CapitalPool.id).limit(1))

    def add(self, pool: CapitalPool) -> CapitalPool:
        self.session.add(pool)
        return pool


class CapitalSlotRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, slot_id: int, *, for_update: bool = False) -> CapitalSlot | None:
        statement = select(CapitalSlot).where(CapitalSlot.id == slot_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_by_no(self, slot_no: int) -> CapitalSlot | None:
        return self.session.scalar(
            select(CapitalSlot).where(CapitalSlot.slot_no == slot_no)
        )

    def list(self) -> list[CapitalSlot]:
        return list(
            self.session.scalars(select(CapitalSlot).order_by(CapitalSlot.slot_no)).all()
        )

    def add(self, slot: CapitalSlot) -> CapitalSlot:
        self.session.add(slot)
        return slot

    def set_status(self, slot: CapitalSlot, status: SlotStatus) -> CapitalSlot:
        slot.status = status
        self.session.add(slot)
        return slot

