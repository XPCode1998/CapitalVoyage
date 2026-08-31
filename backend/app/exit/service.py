from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit.service import AuditService, model_snapshot
from app.capital.repository import CapitalSlotRepository
from app.core.decimal import quantize_fee
from app.core.enums import AuditAction, SlotStatus, VoyageStatus
from app.core.errors import DomainError
from app.core.time import now_shanghai
from app.exit.models import ExitAllocation, ExitTransaction
from app.exit.repository import ExitRepository
from app.exit.schemas import ExitCreate
from app.voyage.models import Voyage
from app.voyage.repository import VoyageRepository


class ExitService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ExitRepository(session)
        self.voyages = VoyageRepository(session)
        self.slots = CapitalSlotRepository(session)
        self.audit = AuditService(session)

    def create(self, payload: ExitCreate) -> ExitTransaction:
        if sum(item.quantity for item in payload.allocations) != payload.total_quantity:
            raise DomainError(
                "INVALID_ALLOCATION",
                "航次分配份额合计必须等于实际卖出份额",
                400,
            )
        voyage_ids = [item.voyage_id for item in payload.allocations]
        if len(voyage_ids) != len(set(voyage_ids)):
            raise DomainError("INVALID_ALLOCATION", "同一航次不能重复分配", 400)

        try:
            # Must happen before loading a Voyage or calculating remaining.
            # SQLite has no row-level SELECT FOR UPDATE, so this harmless UPDATE
            # obtains its database writer lock and serializes exit validation.
            self.voyages.acquire_ledger_write_lock()
            selected: list[tuple[Voyage, int]] = []
            for item in payload.allocations:
                voyage = self.voyages.get(item.voyage_id)
                if voyage is None:
                    raise DomainError("VOYAGE_NOT_FOUND", "分配的航次不存在", 404)
                if voyage.status != VoyageStatus.OPEN:
                    raise DomainError("VOYAGE_CLOSED", "分配的航次已结束", 409)
                if voyage.symbol != payload.symbol:
                    raise DomainError("INVALID_ALLOCATION", "卖出标的与航次不一致", 400)
                if payload.exit_time < voyage.sellable_at:
                    raise DomainError("NOT_SELLABLE", "航次当前不可卖", 409)
                remaining = self.voyages.remaining_quantity(voyage)
                if item.quantity > remaining:
                    raise DomainError(
                        "INVALID_QUANTITY",
                        f"{voyage.voyage_no} 分配份额超过在航份额",
                        400,
                    )
                selected.append((voyage, item.quantity))

            transaction = self.repository.add_transaction(
                ExitTransaction(
                    symbol=payload.symbol,
                    exit_time=payload.exit_time,
                    exit_price=payload.exit_price,
                    total_quantity=payload.total_quantity,
                    total_fee=payload.total_fee,
                )
            )
            self.session.flush()

            allocated_so_far = Decimal("0")
            for index, (voyage, quantity) in enumerate(selected):
                if index == len(selected) - 1:
                    allocated_fee = payload.total_fee - allocated_so_far
                else:
                    proportional = quantize_fee(
                        payload.total_fee * Decimal(quantity) / Decimal(payload.total_quantity)
                    )
                    allocated_fee = min(proportional, payload.total_fee - allocated_so_far)
                    allocated_so_far += allocated_fee

                realized_cost = voyage.unit_cost * Decimal(quantity)
                realized_proceeds = payload.exit_price * Decimal(quantity) - allocated_fee
                realized_profit = realized_proceeds - realized_cost
                realized_return = realized_profit / realized_cost
                allocation = ExitAllocation(
                    exit_transaction_id=transaction.id,
                    voyage_id=voyage.id,
                    quantity=quantity,
                    allocated_fee=allocated_fee,
                    realized_cost=realized_cost,
                    realized_profit=realized_profit,
                    realized_return=realized_return,
                )
                self.repository.add_allocation(allocation)

            self.session.flush()

            for voyage, _quantity in selected:
                remaining = self.voyages.remaining_quantity(voyage)
                if remaining < 0:
                    raise DomainError(
                        "INVALID_QUANTITY",
                        f"{voyage.voyage_no} 返航份额超过在航份额",
                        409,
                    )
                slot = self.slots.get(voyage.slot_id, for_update=True)
                if slot is None:
                    raise DomainError("SLOT_NOT_FOUND", "航次关联的舱位不存在", 500)
                if remaining == 0:
                    voyage.status = VoyageStatus.CLOSED
                    self.slots.set_status(slot, SlotStatus.AVAILABLE)
                else:
                    voyage.status = VoyageStatus.OPEN
                    self.slots.set_status(slot, SlotStatus.OCCUPIED)
                voyage.updated_at = now_shanghai()

            self.session.flush()
            self.audit.record(
                AuditAction.CREATE_EXIT,
                "ExitTransaction",
                transaction.id,
                after={
                    **model_snapshot(transaction),
                    "allocations": [
                        model_snapshot(allocation) for allocation in transaction.allocations
                    ],
                },
            )
            # ExitAllocation rows are written through their foreign keys. Expire
            # any previously loaded collections so the non-persisted model
            # property cannot report a cached pre-exit quantity after commit.
            for voyage, _quantity in selected:
                self.session.expire(voyage, ["exit_allocations"])
            self.session.commit()
        except DomainError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            raise DomainError("DATABASE_ERROR", "记录返航失败", 500) from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise DomainError("DATABASE_ERROR", "记录返航失败", 500) from exc

        result = self.repository.get(transaction.id)
        if result is None:  # pragma: no cover - defensive after a successful commit
            raise DomainError("DATABASE_ERROR", "返航记录未能读取", 500)
        return result

    def get(self, transaction_id: int) -> ExitTransaction:
        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise DomainError("DATABASE_ERROR", "返航记录不存在", 404)
        return transaction

    def list(self) -> list[ExitTransaction]:
        return self.repository.list()
