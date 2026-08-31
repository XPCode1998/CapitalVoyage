from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.capital.service import CapitalService
from app.core.enums import RuntimeState, SettlementMode
from app.core.time import now_shanghai
from app.db.session import get_db
from app.main import app
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.return_engine.monitor import MonitorState
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.voyage.schemas import VoyageCreate
from app.voyage.service import VoyageService


def test_dashboard_exposes_all_routes_and_groups_etf_airports(initialized_db_session):
    now = now_shanghai()
    security_service = SecurityService(initialized_db_session)
    security_service.create(
        SecurityCreate(
            symbol="510300",
            name="沪深300ETF",
            settlement_mode=SettlementMode.T1,
        )
    )
    security_service.create(
        SecurityCreate(
            symbol="588000",
            name="科创50ETF",
            settlement_mode=SettlementMode.T1,
        )
    )
    slots = CapitalService(initialized_db_session).list_slots()
    voyage_service = VoyageService(initialized_db_session)

    def create_voyage(slot_index: int, symbol: str, entry_price: str):
        return voyage_service.create(
            VoyageCreate(
                slot_id=slots[slot_index].id,
                symbol=symbol,
                entry_time=now - timedelta(days=2),
                entry_price=Decimal(entry_price),
                entry_quantity=1000,
                entry_fee=Decimal("0"),
                target_return=Decimal("0.02"),
                sellable_at=now - timedelta(days=1),
            )
        )

    negative = create_voyage(0, "510300", "4.100")
    ready = create_voyage(1, "510300", "4.000")
    waiting = create_voyage(2, "588000", "1.000")
    approaching = create_voyage(3, "510300", "4.000")
    initialized_db_session.add_all(
        [
            MonitorState(
                voyage_id=negative.id,
                runtime_state=RuntimeState.IN_FLIGHT.value,
                last_price=Decimal("4.000"),
                last_return_rate=Decimal("-0.01"),
                last_quote_time=now,
                updated_at=now,
            ),
            MonitorState(
                voyage_id=ready.id,
                runtime_state=RuntimeState.READY_TO_RETURN.value,
                last_price=Decimal("4.100"),
                last_return_rate=Decimal("0.025"),
                last_quote_time=now,
                updated_at=now,
            ),
            MonitorState(
                voyage_id=waiting.id,
                runtime_state=RuntimeState.QUOTE_STALE.value,
                last_price=Decimal("1.000"),
                last_return_rate=Decimal("0.01"),
                last_quote_time=now - timedelta(minutes=5),
                updated_at=now,
            ),
            MonitorState(
                voyage_id=approaching.id,
                runtime_state=RuntimeState.IN_FLIGHT.value,
                last_price=Decimal("4.064"),
                last_return_rate=Decimal("0.016"),
                last_quote_time=now,
                updated_at=now,
            ),
        ]
    )
    initialized_db_session.commit()

    cache = QuoteCache(30)
    cache.set(
        Quote(
            symbol="510300",
            name="沪深300ETF",
            last_price=Decimal("4.100"),
            bid1=Decimal("4.100"),
            ask1=Decimal("4.101"),
            quote_time=now,
            received_at=now,
            source="test",
        )
    )

    def override_db():
        yield initialized_db_session

    app.dependency_overrides[get_db] = override_db
    app.state.runtime = SimpleNamespace(quote_cache=cache)
    client = TestClient(app)
    try:
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()["data"]
    finally:
        app.dependency_overrides.clear()

    assert len(data["routes"]) == 4
    by_voyage = {route["voyage_no"]: route for route in data["routes"]}
    assert by_voyage[negative.voyage_no]["visual_state"] == "PARKED_NEGATIVE"
    assert by_voyage[negative.voyage_no]["capital_amount"] == "4100.000"
    assert by_voyage[negative.voyage_no]["progress"] == "0"
    assert by_voyage[ready.voyage_no]["visual_state"] == "READY"
    assert by_voyage[ready.voyage_no]["progress"] == "1"
    assert by_voyage[approaching.voyage_no]["visual_state"] == "APPROACHING"
    assert by_voyage[approaching.voyage_no]["progress"] == "0.8"
    assert by_voyage[waiting.voyage_no]["visual_state"] == "WAITING_QUOTE"

    by_symbol = {airport["symbol"]: airport for airport in data["airports"]}
    assert by_symbol["510300"] == {
        "symbol": "510300",
        "name": "沪深300ETF",
        "flight_count": 3,
        "negative_count": 1,
        "waiting_count": 0,
        "alarm": True,
        "status": "ALERT",
    }
    assert by_symbol["588000"]["status"] == "WAITING"
