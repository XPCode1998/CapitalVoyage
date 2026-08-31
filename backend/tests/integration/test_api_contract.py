from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.market.cache import QuoteCache


def test_api_uniform_envelope_decimal_strings_and_core_routes(initialized_db_session):
    def override_db():
        yield initialized_db_session

    app.dependency_overrides[get_db] = override_db
    app.state.runtime = SimpleNamespace(
        quote_cache=QuoteCache(30),
        poller=SimpleNamespace(last_error=None),
    )
    client = TestClient(app)
    try:
        settings = client.get("/api/settings")
        assert settings.status_code == 200
        assert settings.json()["error"] is None
        assert settings.json()["data"]["total_capital"] == "500000"

        created = client.post(
            "/api/voyages",
            json={
                "slot_id": 1,
                "symbol": "510300",
                "entry_time": "2026-08-28T10:00:00+08:00",
                "entry_price": "4.000",
                "entry_quantity": 12500,
                "entry_fee": "0",
                "target_return": "0.02",
                "sellable_at": "2026-08-31T09:30:00+08:00",
            },
        )
        assert created.status_code == 201
        assert created.json()["data"]["entry_price"] == "4.000"
        assert created.json()["data"]["voyage_no"] == "QC-0001"

        slots = client.get("/api/slots").json()["data"]
        assert slots[0]["status"] == "OCCUPIED"
        assert slots[0]["voyage"]["remaining_quantity"] == 12500

        mismatch = client.post(
            "/api/exits",
            json={
                "symbol": "510300",
                "exit_time": "2026-08-31T10:30:00+08:00",
                "exit_price": "4.100",
                "total_quantity": 100,
                "total_fee": "1",
                "allocations": [{"voyage_id": created.json()["data"]["id"], "quantity": 99}],
            },
        )
        assert mismatch.status_code == 400
        assert mismatch.json() == {"data": None, "error": {"code": "INVALID_ALLOCATION", "message": "航次分配份额合计必须等于实际卖出份额"}}

        reconciled = client.post("/api/reconcile", json={"symbol": "510300", "broker_quantity": 12500})
        assert reconciled.json()["data"]["matched"] is True
    finally:
        app.dependency_overrides.clear()

