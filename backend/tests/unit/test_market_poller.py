from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.capital.service import CapitalService
from app.core.enums import SettlementMode
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.market.poller import MarketPoller
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.voyage.schemas import VoyageCreate
from app.voyage.service import VoyageService


SHANGHAI = ZoneInfo("Asia/Shanghai")
ENTRY_TIME = datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
SELLABLE_AT = datetime(2026, 8, 31, 9, 30, tzinfo=SHANGHAI)


class StubProvider:
    def __init__(self, outcomes: list[dict[str, Quote] | Exception]) -> None:
        self.outcomes = deque(outcomes)
        self.calls: list[set[str]] = []

    def get_quotes(self, symbols: set[str]) -> dict[str, Quote]:
        self.calls.append(set(symbols))
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MustNotBeCalledProvider:
    def get_quotes(self, symbols: set[str]) -> dict[str, Quote]:
        raise AssertionError(f"provider should not be called for {symbols}")


def _quote(symbol: str, price: str) -> Quote:
    observed_at = datetime(2026, 8, 28, 10, 30, tzinfo=SHANGHAI)
    return Quote(
        symbol=symbol,
        name=f"ETF-{symbol}",
        last_price=Decimal(price),
        bid1=Decimal(price),
        ask1=Decimal(price) + Decimal("0.001"),
        quote_time=observed_at,
        received_at=observed_at,
        source="stub",
    )


def _session_factory(session: Session):
    return sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


def _create_security(session: Session, symbol: str) -> None:
    SecurityService(session).create(
        SecurityCreate(
            symbol=symbol,
            name=f"ETF-{symbol}",
            settlement_mode=SettlementMode.T1,
        )
    )


def _create_voyage(session: Session, slot_id: int, symbol: str):
    return VoyageService(session).create(
        VoyageCreate(
            slot_id=slot_id,
            symbol=symbol,
            entry_time=ENTRY_TIME,
            entry_price=Decimal("4.000"),
            entry_quantity=12_500,
            entry_fee=Decimal("0"),
            target_return=Decimal("0.02"),
            sellable_at=SELLABLE_AT,
        )
    )


def test_poll_deduplicates_open_symbols_updates_cache_and_calls_monitor_hook(
    initialized_db_session: Session,
) -> None:
    for symbol in ("510300", "512880", "159915"):
        _create_security(initialized_db_session, symbol)
    slots = CapitalService(initialized_db_session).list_slots()
    _create_voyage(initialized_db_session, slots[0].id, "510300")
    _create_voyage(initialized_db_session, slots[1].id, "510300")
    _create_voyage(initialized_db_session, slots[2].id, "512880")
    cancelled = _create_voyage(initialized_db_session, slots[3].id, "159915")
    VoyageService(initialized_db_session).cancel(cancelled.id)

    quotes = {
        "510300": _quote("510300", "4.100"),
        "512880": _quote("512880", "1.250"),
    }
    provider = StubProvider([quotes])
    cache = QuoteCache(stale_after_seconds=30)
    callback_values: list[dict[str, Quote]] = []
    poller = MarketPoller(
        provider,  # type: ignore[arg-type]
        cache,
        session_factory=_session_factory(initialized_db_session),
        on_quotes=lambda values: callback_values.append(dict(values)),
    )

    result = poller.poll_once()

    assert result.success is True
    assert result.symbols == frozenset({"510300", "512880"})
    assert provider.calls == [{"510300", "512880"}]
    assert cache.get("510300") == quotes["510300"]
    assert cache.get("512880") == quotes["512880"]
    assert callback_values == [quotes]
    assert poller.consecutive_failures == 0
    assert poller.next_interval_seconds == 15


def test_provider_failure_keeps_last_cached_quote_and_skips_callback(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session, "510300")
    slot = CapitalService(initialized_db_session).list_slots()[0]
    _create_voyage(initialized_db_session, slot.id, "510300")
    cached = _quote("510300", "4.000")
    cache = QuoteCache(stale_after_seconds=30)
    cache.set(cached)
    failure = RuntimeError("provider unavailable")
    provider = StubProvider([failure])
    callback_values: list[dict[str, Quote]] = []
    poller = MarketPoller(
        provider,  # type: ignore[arg-type]
        cache,
        session_factory=_session_factory(initialized_db_session),
        on_quotes=lambda values: callback_values.append(dict(values)),
    )

    result = poller.poll_once()

    assert result.success is False
    assert result.error is failure
    assert cache.get("510300") == cached
    assert callback_values == []
    assert poller.consecutive_failures == 1
    assert poller.next_interval_seconds == 15


def test_failures_back_off_to_cap_and_success_restores_normal_interval(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session, "510300")
    slot = CapitalService(initialized_db_session).list_slots()[0]
    _create_voyage(initialized_db_session, slot.id, "510300")
    failures = [RuntimeError(f"failure-{index}") for index in range(6)]
    recovered = {"510300": _quote("510300", "4.200")}
    provider = StubProvider([*failures, recovered])
    poller = MarketPoller(
        provider,  # type: ignore[arg-type]
        QuoteCache(stale_after_seconds=30),
        session_factory=_session_factory(initialized_db_session),
    )

    observed_delays = [poller.poll_once().next_interval_seconds for _ in failures]

    assert observed_delays == [15, 30, 60, 120, 300, 300]
    assert poller.consecutive_failures == 6
    recovery = poller.poll_once()
    assert recovery.success is True
    assert poller.consecutive_failures == 0
    assert poller.next_interval_seconds == 15
    assert poller.last_error is None


def test_no_open_voyages_is_success_without_provider_request(
    initialized_db_session: Session,
) -> None:
    poller = MarketPoller(
        MustNotBeCalledProvider(),  # type: ignore[arg-type]
        QuoteCache(stale_after_seconds=30),
        session_factory=_session_factory(initialized_db_session),
    )

    result = poller.poll_once()

    assert result.success is True
    assert result.symbols == frozenset()
    assert result.quotes == {}
    assert result.next_interval_seconds == 15


def test_callback_failure_does_not_reclassify_successful_market_fetch(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session, "510300")
    slot = CapitalService(initialized_db_session).list_slots()[0]
    _create_voyage(initialized_db_session, slot.id, "510300")
    quote = _quote("510300", "4.100")
    cache = QuoteCache(stale_after_seconds=30)

    def broken_callback(_quotes: Any) -> None:
        raise RuntimeError("monitor failed")

    poller = MarketPoller(
        StubProvider([{"510300": quote}]),  # type: ignore[arg-type]
        cache,
        session_factory=_session_factory(initialized_db_session),
        on_quotes=broken_callback,
    )

    result = poller.poll_once()

    assert result.success is True
    assert isinstance(result.callback_error, RuntimeError)
    assert cache.get("510300") == quote
    assert poller.consecutive_failures == 0
    assert poller.next_interval_seconds == 15
