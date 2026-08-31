from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.calendar.service import TradingCalendar
from app.core.enums import ReturnPriceMode, RuntimeState, VoyageStatus
from app.core.errors import DomainError
from app.core.time import now_shanghai
from app.market.cache import QuoteCache
from app.return_engine.engine import ReturnEngine
from app.return_engine.fee import FeeCalculator
from app.return_engine.schemas import ReadyVoyage, ReturnGroup
from app.voyage.models import Voyage
from app.voyage.repository import VoyageRepository


NowFactory = Callable[[], datetime]


@dataclass(slots=True)
class _GroupAccumulator:
    symbol: str
    name: str
    system_total_quantity: int = 0
    ready_quantity: int = 0
    ready_voyages: list[ReadyVoyage] = field(default_factory=list)


class ReturnCenterService:
    """Build fee-aware, freshness-safe return groups from OPEN Voyages."""

    def __init__(
        self,
        session: Session,
        quote_cache: QuoteCache,
        *,
        fee_calculator: FeeCalculator | None = None,
        return_engine: ReturnEngine | None = None,
        now_factory: NowFactory = now_shanghai,
        price_mode: ReturnPriceMode | str = ReturnPriceMode.BID1,
        trading_calendar: TradingCalendar | None = None,
    ) -> None:
        if return_engine is not None and fee_calculator is not None:
            raise ValueError("inject either return_engine or fee_calculator, not both")
        if not callable(now_factory):
            raise TypeError("now_factory must be callable")

        self.session = session
        self.quote_cache = quote_cache
        self.return_engine = return_engine or ReturnEngine(fee_calculator)
        self.now_factory = now_factory
        self.price_mode = ReturnPriceMode(price_mode)
        self.trading_calendar = trading_calendar or TradingCalendar()
        self.voyages = VoyageRepository(session)

    def get_ready(self, *, now: datetime | None = None) -> list[ReturnGroup]:
        observed_at = now if now is not None else self.now_factory()
        self._require_aware(observed_at)
        accumulators: dict[str, _GroupAccumulator] = {}

        open_voyages = self.voyages.list(status=VoyageStatus.OPEN)
        for voyage in open_voyages:
            remaining = self.voyages.remaining_quantity(voyage)
            if remaining < 0:
                raise DomainError(
                    "DATABASE_ERROR",
                    f"{voyage.voyage_no} 的在航份额为负数",
                    500,
                )
            if remaining == 0:
                # A zero-remaining OPEN row is inconsistent but cannot be passed
                # into ReturnEngine. It contributes neither holding nor readiness.
                continue

            accumulator = accumulators.get(voyage.symbol)
            if accumulator is None:
                accumulator = _GroupAccumulator(
                    symbol=voyage.symbol,
                    name=self._security_name(voyage),
                )
                accumulators[voyage.symbol] = accumulator
            accumulator.system_total_quantity += remaining

            quote = self.quote_cache.get(voyage.symbol)
            market_open = self.trading_calendar.is_market_open(observed_at)
            if quote is None or not self.quote_cache.is_usable(quote, market_open=market_open, now=observed_at):
                continue

            sellable = observed_at >= voyage.sellable_at
            monitor_price = quote.price_for(self.price_mode) if market_open else quote.last_price
            runtime = self.return_engine.calculate(
                voyage_id=voyage.id,
                entry_price=voyage.entry_price,
                entry_quantity=voyage.entry_quantity,
                entry_fee=voyage.entry_fee,
                remaining_quantity=remaining,
                monitor_price=monitor_price,
                target_return=voyage.target_return,
                sellable=sellable,
            )
            if not sellable or runtime.net_return < voyage.target_return:
                continue

            accumulator.ready_quantity += remaining
            accumulator.ready_voyages.append(
                ReadyVoyage(
                    voyage_no=voyage.voyage_no,
                    remaining_quantity=remaining,
                    entry_price=voyage.entry_price,
                    monitor_price=runtime.monitor_price,
                    net_return=runtime.net_return,
                    target_return=runtime.target_return,
                    runtime_state=runtime.runtime_state,
                )
            )

        return [
            ReturnGroup(
                symbol=accumulator.symbol,
                name=accumulator.name,
                system_total_quantity=accumulator.system_total_quantity,
                ready_quantity=accumulator.ready_quantity,
                ready_voyages=sorted(
                    accumulator.ready_voyages,
                    key=lambda item: item.voyage_no,
                ),
            )
            for accumulator in sorted(accumulators.values(), key=lambda item: item.symbol)
            if accumulator.ready_quantity > 0
        ]

    @staticmethod
    def _security_name(voyage: Voyage) -> str:
        security = voyage.security
        return security.name if security is not None else voyage.symbol

    @staticmethod
    def _require_aware(value: datetime) -> None:
        if not isinstance(value, datetime):
            raise TypeError("now must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
