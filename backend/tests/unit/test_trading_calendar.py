from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

import app.calendar.service as calendar_module
from app.calendar.service import TradingCalendar
from app.capital.service import CapitalService
from app.core.enums import SettlementMode
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.voyage.schemas import VoyageCreate
from app.voyage.service import VoyageService


SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_sse_trading_days_include_exchange_holidays() -> None:
    calendar = TradingCalendar()

    assert calendar.using_fallback is False
    assert calendar.is_trading_day(date(2026, 8, 28)) is True
    assert calendar.is_trading_day(date(2026, 8, 29)) is False
    assert calendar.is_trading_day(date(2026, 10, 1)) is False
    assert calendar.is_trading_day(date(2026, 10, 8)) is True


def test_next_trading_day_skips_weekends_and_national_day_holiday() -> None:
    calendar = TradingCalendar()

    assert calendar.next_trading_day(date(2026, 8, 28)) == date(2026, 8, 31)
    assert calendar.next_trading_day(date(2026, 9, 30)) == date(2026, 10, 8)


def test_trading_days_between_excludes_start_and_includes_end() -> None:
    calendar = TradingCalendar()

    assert calendar.trading_days_between(date(2026, 8, 25), date(2026, 8, 28)) == 3
    assert calendar.trading_days_between(date(2026, 8, 28), date(2026, 8, 31)) == 1
    assert calendar.trading_days_between(date(2026, 8, 28), date(2026, 8, 28)) == 0
    assert calendar.trading_days_between(date(2026, 8, 31), date(2026, 8, 28)) == 0


def test_market_open_uses_shanghai_sessions_and_excludes_lunch_break() -> None:
    calendar = TradingCalendar()

    assert calendar.is_market_open(
        datetime(2026, 8, 28, 9, 30, tzinfo=SHANGHAI)
    )
    assert calendar.is_market_open(
        datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
    )
    assert not calendar.is_market_open(
        datetime(2026, 8, 28, 12, 0, tzinfo=SHANGHAI)
    )
    assert calendar.is_market_open(
        datetime(2026, 8, 28, 13, 0, tzinfo=SHANGHAI)
    )
    assert not calendar.is_market_open(
        datetime(2026, 8, 28, 15, 0, tzinfo=SHANGHAI)
    )
    assert not calendar.is_market_open(
        datetime(2026, 8, 29, 10, 0, tzinfo=SHANGHAI)
    )
    assert calendar.is_market_open(
        datetime(2026, 8, 28, 2, 0, tzinfo=timezone.utc)
    )


def test_calculate_sellable_at_supports_t0_t1_and_conservative_custom() -> None:
    calendar = TradingCalendar()
    friday_entry = datetime(2026, 8, 28, 10, 15, tzinfo=SHANGHAI)

    assert calendar.calculate_sellable_at(friday_entry, SettlementMode.T0) == friday_entry
    assert calendar.calculate_sellable_at(
        friday_entry, SettlementMode.T1
    ) == datetime(2026, 8, 31, 9, 30, tzinfo=SHANGHAI)
    assert calendar.calculate_sellable_at(
        friday_entry, SettlementMode.CUSTOM
    ) == datetime(2026, 8, 31, 9, 30, tzinfo=SHANGHAI)

    before_national_day = datetime(2026, 9, 30, 14, 0, tzinfo=SHANGHAI)
    assert calendar.calculate_sellable_at(
        before_national_day, SettlementMode.T1
    ) == datetime(2026, 10, 8, 9, 30, tzinfo=SHANGHAI)


def test_naive_datetimes_are_interpreted_as_shanghai_time() -> None:
    calendar = TradingCalendar()
    naive_entry = datetime(2026, 8, 28, 10, 15)

    sellable_at = calendar.calculate_sellable_at(naive_entry, SettlementMode.T0)

    assert sellable_at == datetime(2026, 8, 28, 10, 15, tzinfo=SHANGHAI)


def test_reliable_fallback_is_only_used_when_sse_dependency_is_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(calendar_module, "mcal", None)
    calendar = TradingCalendar()

    assert calendar.using_fallback is True
    assert calendar.is_trading_day(date(2026, 8, 28)) is True
    assert calendar.is_trading_day(date(2026, 8, 29)) is False
    assert calendar.is_trading_day(date(2026, 10, 1)) is False
    assert calendar.next_trading_day(date(2026, 8, 28)) == date(2026, 8, 31)
    assert calendar.next_trading_day(date(2026, 9, 30)) == date(2026, 10, 8)
    assert calendar.is_market_open(
        datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
    )
    assert not calendar.is_market_open(
        datetime(2026, 8, 28, 12, 0, tzinfo=SHANGHAI)
    )


def _create_security(
    session: Session,
    symbol: str,
    settlement_mode: SettlementMode,
) -> None:
    SecurityService(session).create(
        SecurityCreate(
            symbol=symbol,
            name=f"ETF-{symbol}",
            settlement_mode=settlement_mode,
        )
    )


def _voyage_payload(
    slot_id: int,
    symbol: str,
    *,
    sellable_at: datetime | None = None,
) -> VoyageCreate:
    return VoyageCreate(
        slot_id=slot_id,
        symbol=symbol,
        entry_time=datetime(2026, 8, 28, 10, 15, tzinfo=SHANGHAI),
        entry_price=Decimal("4.000"),
        entry_quantity=12_500,
        entry_fee=Decimal("5"),
        target_return=Decimal("0.02"),
        sellable_at=sellable_at,
    )


def test_voyage_service_calculates_sellable_at_from_security(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session, "510300", SettlementMode.T1)
    slot = CapitalService(initialized_db_session).list_slots()[0]

    voyage = VoyageService(initialized_db_session).create(
        _voyage_payload(slot.id, "510300")
    )

    assert voyage.sellable_at == datetime(2026, 8, 31, 9, 30, tzinfo=SHANGHAI)


def test_voyage_service_preserves_explicit_sellable_at_override(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session, "510300", SettlementMode.T1)
    slot = CapitalService(initialized_db_session).list_slots()[0]
    override = datetime(2026, 9, 1, 9, 30, tzinfo=SHANGHAI)

    voyage = VoyageService(initialized_db_session).create(
        _voyage_payload(slot.id, "510300", sellable_at=override)
    )

    assert voyage.sellable_at == override
