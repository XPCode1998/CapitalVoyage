from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import AuditService, model_snapshot
from app.calendar.service import TradingCalendar
from app.capital.repository import CapitalSlotRepository
from app.core.enums import AuditAction, SlotStatus, VoyageStatus
from app.core.errors import DomainError
from app.core.time import now_shanghai
from app.security.repository import SecurityRepository
from app.voyage.models import Voyage
from app.voyage.repository import VoyageRepository
from app.voyage.schemas import VoyageCreate, VoyageUpdate


class VoyageService:
    def __init__(
        self,
        session: Session,
        trading_calendar: TradingCalendar | None = None,
    ):
        self.session = session
        self.repository = VoyageRepository(session)
        self.slots = CapitalSlotRepository(session)
        self.securities = SecurityRepository(session)
        self.audit = AuditService(session)
        self.trading_calendar = trading_calendar or TradingCalendar()

    @contextmanager
    def _rollback_on_error(self) -> Iterator[None]:
        """Never leave the SQLite writer lock held after a domain failure."""

        try:
            yield
        except Exception:
            self.session.rollback()
            raise

    def create(self, payload: VoyageCreate) -> Voyage:
        try:
            self.repository.acquire_ledger_write_lock()
            slot = self.slots.get(payload.slot_id, for_update=True)
            if slot is None:
                raise DomainError("SLOT_NOT_FOUND", "舱位不存在", 404)
            if (
                slot.status != SlotStatus.AVAILABLE
                or self.repository.has_open_for_slot(slot.id)
            ):
                raise DomainError("SLOT_OCCUPIED", "舱位已有在航航次", 409)

            security = self.securities.get(payload.symbol)
            if security is None or not security.enabled:
                raise DomainError("SECURITY_NOT_FOUND", "证券不存在或已停用", 404)

            values = payload.model_dump()
            if values["sellable_at"] is None:
                values["sellable_at"] = self.trading_calendar.calculate_sellable_at(
                    payload.entry_time,
                    security.settlement_mode,
                )
            values["voyage_no"] = self.repository.next_voyage_no()
            values["status"] = VoyageStatus.OPEN
            voyage = self.repository.add(Voyage(**values))
            self.slots.set_status(slot, SlotStatus.OCCUPIED)
            self.session.flush()
            self.audit.record(
                AuditAction.CREATE_VOYAGE,
                "Voyage",
                voyage.id,
                after=model_snapshot(voyage),
            )
            self.session.commit()
        except DomainError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            if "uq_voyages_one_open_per_slot" in str(exc) or "voyages.slot_id" in str(exc):
                raise DomainError("SLOT_OCCUPIED", "舱位已有在航航次", 409) from exc
            raise DomainError("DATABASE_ERROR", "创建航次失败", 500) from exc

        self.session.refresh(voyage)
        return voyage

    def get(self, voyage_id: int) -> Voyage:
        voyage = self.repository.get(voyage_id, with_allocations=True)
        if voyage is None:
            raise DomainError("VOYAGE_NOT_FOUND", "航次不存在", 404)
        return voyage

    def list(self, *, status: VoyageStatus | None = None) -> list[Voyage]:
        return self.repository.list(status=status)

    def remaining_quantity(self, voyage_id: int) -> int:
        voyage = self.repository.get(voyage_id)
        if voyage is None:
            raise DomainError("VOYAGE_NOT_FOUND", "航次不存在", 404)
        return self.repository.remaining_quantity(voyage)

    def update(self, voyage_id: int, payload: VoyageUpdate) -> Voyage:
        with self._rollback_on_error():
            self.repository.acquire_ledger_write_lock()
            voyage = self.get(voyage_id)
            if voyage.status != VoyageStatus.OPEN:
                raise DomainError("VOYAGE_CLOSED", "仅在航航次可修改", 409)

            changes = payload.model_dump(exclude_unset=True, exclude_none=True)
            if "entry_time" in changes and "sellable_at" not in changes:
                security = voyage.security
                if security is None:
                    raise DomainError("SECURITY_NOT_FOUND", "航次证券信息不存在", 404)
                changes["sellable_at"] = self.trading_calendar.calculate_sellable_at(
                    changes["entry_time"],
                    security.settlement_mode,
                )
            allocated = self.repository.allocated_quantity(voyage.id)
            accounting_fields = {"entry_time", "entry_price", "entry_quantity", "entry_fee"}
            if allocated and accounting_fields.intersection(changes):
                raise DomainError(
                    "INVALID_ALLOCATION",
                    "已有返航记录后不能修改航次成本或买入份额",
                    409,
                )
            if "entry_quantity" in changes and changes["entry_quantity"] < allocated:
                raise DomainError("INVALID_QUANTITY", "买入份额不能小于已返航份额", 400)

            before = model_snapshot(voyage)
            for field, value in changes.items():
                setattr(voyage, field, value)
            voyage.updated_at = now_shanghai()
            self.session.flush()
            self.audit.record(
                AuditAction.UPDATE_VOYAGE,
                "Voyage",
                voyage.id,
                before=before,
                after=model_snapshot(voyage),
            )
            self.session.commit()
            self.session.refresh(voyage)
        return voyage

    def cancel(self, voyage_id: int) -> Voyage:
        with self._rollback_on_error():
            self.repository.acquire_ledger_write_lock()
            voyage = self.get(voyage_id)
            if voyage.status != VoyageStatus.OPEN:
                raise DomainError("VOYAGE_CLOSED", "仅在航航次可取消", 409)
            if self.repository.allocated_quantity(voyage.id) > 0:
                raise DomainError("INVALID_ALLOCATION", "已有返航记录的航次不能取消", 409)

            slot = self.slots.get(voyage.slot_id, for_update=True)
            if slot is None:
                raise DomainError("SLOT_NOT_FOUND", "舱位不存在", 404)
            before = model_snapshot(voyage)
            voyage.status = VoyageStatus.CANCELLED
            voyage.updated_at = now_shanghai()
            self.slots.set_status(slot, SlotStatus.AVAILABLE)
            self.session.flush()
            self.audit.record(
                AuditAction.CANCEL_VOYAGE,
                "Voyage",
                voyage.id,
                before=before,
                after=model_snapshot(voyage),
            )
            self.session.commit()
            self.session.refresh(voyage)
        return voyage
