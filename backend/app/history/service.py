from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calendar.service import TradingCalendar
from app.capital.service import CapitalService
from app.core.enums import VoyageStatus
from app.exit.models import ExitAllocation
from app.voyage.models import Voyage
from app.voyage.repository import VoyageRepository


class HistoryService:
    def __init__(self, session: Session):
        self.session = session
        self.calendar = TradingCalendar()
        self.voyages = VoyageRepository(session)

    def get(self) -> dict:
        rows = list(self.session.scalars(select(Voyage).where(Voyage.status == VoyageStatus.CLOSED).options(selectinload(Voyage.exit_allocations).selectinload(ExitAllocation.exit_transaction)).order_by(Voyage.id.desc())).all())
        records, total_profit, durations = [], Decimal("0"), []
        for voyage in rows:
            allocations = voyage.exit_allocations
            profit = sum((a.realized_profit for a in allocations), Decimal("0"))
            cost = sum((a.realized_cost for a in allocations), Decimal("0"))
            quantity = sum((a.quantity for a in allocations), 0)
            total_fee = sum((a.allocated_fee for a in allocations), Decimal("0"))
            exit_amount = sum(
                (a.exit_transaction.exit_price * a.quantity for a in allocations),
                Decimal("0"),
            )
            exit_time = max((a.exit_transaction.exit_time for a in allocations), default=voyage.updated_at)
            duration = self.calendar.trading_days_between(voyage.entry_time, exit_time)
            total_profit += profit; durations.append(duration)
            records.append({"id": voyage.id, "voyage_no": voyage.voyage_no, "symbol": voyage.symbol, "name": voyage.security.name, "entry_time": voyage.entry_time, "entry_price": voyage.entry_price, "entry_cost": cost, "exit_time": exit_time, "exit_price": allocations[-1].exit_transaction.exit_price if allocations else None, "exit_amount": exit_amount, "quantity": quantity, "total_fee": total_fee, "realized_profit": profit, "realized_return": profit / cost if cost else Decimal("0"), "trading_days": duration})
        open_count = len(self.voyages.list(status=VoyageStatus.OPEN))
        completed = len(records)
        slot_count = max(len(CapitalService(self.session).list_slots()), 1)
        return {"stats": {"completed_voyages": completed, "total_realized_profit": total_profit, "average_voyage_days": (sum(durations) / completed if completed else 0), "longest_voyage_days": max(durations, default=0), "current_stranded": open_count, "average_turnover": Decimal(completed) / Decimal(slot_count)}, "records": records}
