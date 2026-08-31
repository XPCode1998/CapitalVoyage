from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.capital.service import CapitalService
from app.core.enums import ReturnPriceMode, RuntimeState, SettlementMode
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.return_engine.center import ReturnCenterService
from app.return_engine.fee import FeeCalculator
from app.return_engine.models import FeeConfig
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.voyage.schemas import VoyageCreate
from app.voyage.service import VoyageService


SHANGHAI = ZoneInfo("Asia/Shanghai")
ENTRY_TIME = datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
SELLABLE_AT = datetime(2026, 8, 31, 9, 30, tzinfo=SHANGHAI)
NOW = datetime(2026, 8, 31, 10, 30, tzinfo=SHANGHAI)


def _create_security(session: Session, symbol: str = "510300") -> None:
    SecurityService(session).create(
        SecurityCreate(
            symbol=symbol,
            name="沪深300ETF华泰柏瑞",
            settlement_mode=SettlementMode.T1,
        )
    )


def _create_voyage(
    session: Session,
    *,
    slot_id: int,
    entry_price: str,
    entry_quantity: int,
    sellable_at: datetime = SELLABLE_AT,
):
    return VoyageService(session).create(
        VoyageCreate(
            slot_id=slot_id,
            symbol="510300",
            entry_time=ENTRY_TIME,
            entry_price=Decimal(entry_price),
            entry_quantity=entry_quantity,
            entry_fee=Decimal("0"),
            target_return=Decimal("0.02"),
            sellable_at=sellable_at,
        )
    )


def _quote(
    *,
    quote_time: datetime = NOW,
    last_price: str = "3.990",
    bid1: str | None = "3.990",
) -> Quote:
    return Quote(
        symbol="510300",
        name="沪深300ETF华泰柏瑞",
        last_price=Decimal(last_price),
        bid1=Decimal(bid1) if bid1 is not None else None,
        ask1=Decimal(last_price) + Decimal("0.001"),
        quote_time=quote_time,
        received_at=quote_time,
        source="stub",
    )


def _service(
    session: Session,
    cache: QuoteCache,
    *,
    price_mode: ReturnPriceMode = ReturnPriceMode.BID1,
) -> ReturnCenterService:
    return ReturnCenterService(
        session,
        cache,
        fee_calculator=FeeCalculator(FeeConfig()),
        now_factory=lambda: NOW,
        price_mode=price_mode,
    )


def test_three_voyages_group_ready_quantity_is_25700(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slots = CapitalService(initialized_db_session).list_slots()
    first = _create_voyage(
        initialized_db_session,
        slot_id=slots[0].id,
        entry_price="4.000",
        entry_quantity=12_500,
    )
    second = _create_voyage(
        initialized_db_session,
        slot_id=slots[1].id,
        entry_price="3.900",
        entry_quantity=12_800,
    )
    third = _create_voyage(
        initialized_db_session,
        slot_id=slots[2].id,
        entry_price="3.850",
        entry_quantity=12_900,
    )
    cache = QuoteCache(stale_after_seconds=30)
    cache.set(_quote())

    groups = _service(initialized_db_session, cache).get_ready()

    assert len(groups) == 1
    group = groups[0]
    assert group.symbol == "510300"
    assert group.name == "沪深300ETF华泰柏瑞"
    assert group.system_total_quantity == 38_200
    assert group.ready_quantity == 25_700
    assert [item.voyage_no for item in group.ready_voyages] == [
        second.voyage_no,
        third.voyage_no,
    ]
    assert first.voyage_no not in {item.voyage_no for item in group.ready_voyages}
    assert [item.remaining_quantity for item in group.ready_voyages] == [12_800, 12_900]
    assert group.ready_voyages[0].entry_price == Decimal("3.900")
    assert group.ready_voyages[0].monitor_price == Decimal("3.990")
    assert group.ready_voyages[0].net_return == (
        Decimal("3.990") - Decimal("3.900")
    ) / Decimal("3.900")
    assert all(
        item.runtime_state == RuntimeState.READY_TO_RETURN
        for item in group.ready_voyages
    )


def test_stale_quote_never_enters_return_center(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = CapitalService(initialized_db_session).list_slots()[0]
    _create_voyage(
        initialized_db_session,
        slot_id=slot.id,
        entry_price="3.850",
        entry_quantity=12_900,
    )
    cache = QuoteCache(stale_after_seconds=30)
    cache.set(_quote(quote_time=NOW - timedelta(seconds=31)))

    assert _service(initialized_db_session, cache).get_ready() == []


def test_market_closed_uses_latest_close_even_when_quote_is_old(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = CapitalService(initialized_db_session).list_slots()[0]
    voyage = _create_voyage(
        initialized_db_session,
        slot_id=slot.id,
        entry_price="3.850",
        entry_quantity=12_900,
        sellable_at=ENTRY_TIME,
    )
    saturday = datetime(2026, 8, 29, 10, 0, tzinfo=SHANGHAI)
    cache = QuoteCache(stale_after_seconds=30)
    cache.set(
        _quote(
            quote_time=datetime(2026, 8, 28, 15, 0, tzinfo=SHANGHAI),
            last_price="3.990",
            bid1="3.800",
        )
    )

    groups = _service(initialized_db_session, cache).get_ready(now=saturday)

    assert groups[0].ready_voyages[0].voyage_no == voyage.voyage_no
    assert groups[0].ready_voyages[0].monitor_price == Decimal("3.990")


def test_target_reached_but_not_sellable_is_excluded(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = CapitalService(initialized_db_session).list_slots()[0]
    _create_voyage(
        initialized_db_session,
        slot_id=slot.id,
        entry_price="3.850",
        entry_quantity=12_900,
        sellable_at=NOW + timedelta(days=1),
    )
    cache = QuoteCache(stale_after_seconds=30)
    cache.set(_quote())

    assert _service(initialized_db_session, cache).get_ready() == []


def test_return_center_honors_injected_price_mode(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = CapitalService(initialized_db_session).list_slots()[0]
    voyage = _create_voyage(
        initialized_db_session,
        slot_id=slot.id,
        entry_price="4.000",
        entry_quantity=12_500,
    )
    cache = QuoteCache(stale_after_seconds=30)
    cache.set(_quote(last_price="4.200", bid1="3.990"))

    assert _service(
        initialized_db_session,
        cache,
        price_mode=ReturnPriceMode.BID1,
    ).get_ready() == []
    last_groups = _service(
        initialized_db_session,
        cache,
        price_mode=ReturnPriceMode.LAST,
    ).get_ready()

    assert last_groups[0].ready_quantity == 12_500
    assert last_groups[0].ready_voyages[0].voyage_no == voyage.voyage_no
    assert last_groups[0].ready_voyages[0].monitor_price == Decimal("4.200")
