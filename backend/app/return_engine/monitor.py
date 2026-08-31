from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.calendar.service import TradingCalendar
from app.core.enums import ReturnPriceMode, RuntimeState, VoyageStatus
from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime, DecimalType
from app.market.cache import QuoteCache
from app.return_engine.engine import ReturnEngine
from app.return_engine.models import RuntimeResult
from app.voyage.models import Voyage
from app.voyage.repository import VoyageRepository


class MonitorState(Base):
    __tablename__ = "monitor_states"

    voyage_id: Mapped[int] = mapped_column(ForeignKey("voyages.id", ondelete="CASCADE"), primary_key=True)
    runtime_state: Mapped[str] = mapped_column(nullable=False)
    last_price: Mapped[Decimal | None] = mapped_column(DecimalType())
    last_return_rate: Mapped[Decimal | None] = mapped_column(DecimalType())
    last_quote_time: Mapped[datetime | None] = mapped_column(AwareDateTime())
    last_notification_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False)


@dataclass(frozen=True, slots=True)
class MonitorEvaluation:
    voyage_id: int
    previous_state: RuntimeState | None
    state: RuntimeState
    runtime: RuntimeResult | None


class MonitorService:
    TARGET_STATES = {RuntimeState.TARGET_REACHED_NOT_SELLABLE, RuntimeState.READY_TO_RETURN}

    def __init__(self, session: Session, cache: QuoteCache, engine: ReturnEngine, *, price_mode: ReturnPriceMode | str = ReturnPriceMode.BID1, trading_calendar: TradingCalendar | None = None):
        self.session = session
        self.cache = cache
        self.engine = engine
        self.price_mode = ReturnPriceMode(price_mode)
        self.trading_calendar = trading_calendar or TradingCalendar()
        self.voyages = VoyageRepository(session)

    def evaluate_all(self, *, now: datetime | None = None, commit: bool = True) -> list[MonitorEvaluation]:
        observed_at = now or now_shanghai()
        results = [self.evaluate(voyage, now=observed_at) for voyage in self.voyages.list(status=VoyageStatus.OPEN)]
        if commit:
            self.session.commit()
        return results

    def evaluate(self, voyage: Voyage, *, now: datetime | None = None) -> MonitorEvaluation:
        observed_at = now or now_shanghai()
        existing = self.session.get(MonitorState, voyage.id)
        previous = RuntimeState(existing.runtime_state) if existing else None
        quote = self.cache.get(voyage.symbol)
        runtime: RuntimeResult | None = None
        market_open = self.trading_calendar.is_market_open(observed_at)
        if quote is None or not self.cache.is_usable(quote, market_open=market_open, now=observed_at):
            state = RuntimeState.QUOTE_STALE
            price = quote.price_for(self.price_mode) if quote else (existing.last_price if existing else None)
            quote_time = quote.quote_time if quote else (existing.last_quote_time if existing else None)
            return_rate = existing.last_return_rate if existing else None
        else:
            remaining = self.voyages.remaining_quantity(voyage)
            monitor_price = quote.price_for(self.price_mode) if market_open else quote.last_price
            runtime = self.engine.calculate(
                voyage_id=voyage.id, entry_price=voyage.entry_price,
                entry_quantity=voyage.entry_quantity, entry_fee=voyage.entry_fee,
                remaining_quantity=remaining, monitor_price=monitor_price,
                target_return=voyage.target_return, sellable=observed_at >= voyage.sellable_at,
            )
            state = runtime.runtime_state
            price, quote_time, return_rate = runtime.monitor_price, quote.quote_time, runtime.net_return
            crossed = state in self.TARGET_STATES and previous not in self.TARGET_STATES
            if crossed:
                if voyage.first_target_reached_at is None:
                    voyage.first_target_reached_at = observed_at
                voyage.last_target_reached_at = observed_at
        if existing is None:
            existing = MonitorState(voyage_id=voyage.id, runtime_state=state.value)
            self.session.add(existing)
        existing.runtime_state = state.value
        existing.last_price = price
        existing.last_return_rate = return_rate
        existing.last_quote_time = quote_time
        existing.updated_at = observed_at
        self.session.flush()
        return MonitorEvaluation(voyage.id, previous, state, runtime)

    def list_states(self) -> list[MonitorState]:
        return list(self.session.scalars(select(MonitorState).order_by(MonitorState.voyage_id)).all())
