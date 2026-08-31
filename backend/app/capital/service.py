from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.capital.models import CapitalPool, CapitalSlot
from app.capital.repository import CapitalPoolRepository, CapitalSlotRepository
from app.capital.schemas import CapitalPoolUpdate
from app.core.enums import SlotStatus
from app.core.errors import DomainError
from app.core.time import now_shanghai


class CapitalService:
    def __init__(self, session: Session):
        self.session = session
        self.pools = CapitalPoolRepository(session)
        self.slots = CapitalSlotRepository(session)

    def initialize_defaults(
        self,
        *,
        total_capital: Decimal = Decimal("500000"),
        slot_count: int = 10,
        slot_amount: Decimal = Decimal("50000"),
        default_target_return: Decimal = Decimal("0.02"),
        commit: bool = True,
    ) -> CapitalPool:
        if total_capital <= 0 or slot_amount <= 0 or default_target_return <= 0:
            raise ValueError("capital, slot amount and target return must be positive")
        if slot_count <= 0:
            raise ValueError("slot_count must be positive")

        pool = self.pools.get()
        if pool is None:
            pool = self.pools.add(
                CapitalPool(
                    name="CapitalVoyage",
                    total_capital=total_capital,
                    default_target_return=default_target_return,
                )
            )

        existing = {slot.slot_no for slot in self.slots.list()}
        for slot_no in range(1, slot_count + 1):
            if slot_no not in existing:
                self.slots.add(
                    CapitalSlot(
                        slot_no=slot_no,
                        budget_amount=slot_amount,
                        status=SlotStatus.AVAILABLE,
                    )
                )

        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(pool)
        return pool

    def get_pool(self) -> CapitalPool:
        pool = self.pools.get()
        if pool is None:
            raise DomainError("DATABASE_ERROR", "资金池尚未初始化", 500)
        return pool

    def update_pool(self, payload: CapitalPoolUpdate) -> CapitalPool:
        pool = self.get_pool()
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(pool, field, value)
        pool.updated_at = now_shanghai()
        self.session.commit()
        self.session.refresh(pool)
        return pool

    def list_slots(self) -> list[CapitalSlot]:
        return self.slots.list()

    def get_slot(self, slot_id: int) -> CapitalSlot:
        slot = self.slots.get(slot_id)
        if slot is None:
            raise DomainError("SLOT_NOT_FOUND", "舱位不存在", 404)
        return slot

