from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.common import success
from app.calendar.service import TradingCalendar
from app.capital.service import CapitalService
from app.core.enums import MarketStatus, QuoteStatus, RuntimeState, VoyageStatus
from app.core.time import now_shanghai
from app.db.session import get_db
from app.return_engine.monitor import MonitorState
from app.voyage.repository import VoyageRepository


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    now = now_shanghai()
    pool = CapitalService(db).get_pool()
    slots = CapitalService(db).list_slots()
    voyages = VoyageRepository(db)
    open_voyages = voyages.list(status=VoyageStatus.OPEN)
    in_flight_capital = Decimal("0")
    ready_capital = Decimal("0")
    near, ready, routes = [], [], []
    airports: dict[str, dict] = {}
    cache = request.app.state.runtime.quote_cache
    market_open = TradingCalendar().is_market_open(now)
    counts = {"in_flight": 0, "near_return": 0, "ready_to_return": 0, "available_slots": sum(1 for s in slots if s.status.value == "AVAILABLE")}
    for voyage in open_voyages:
        remaining = voyages.remaining_quantity(voyage)
        cost = voyage.unit_cost * remaining
        monitor = db.get(MonitorState, voyage.id)
        state = RuntimeState(monitor.runtime_state) if monitor else RuntimeState.QUOTE_STALE
        if state == RuntimeState.READY_TO_RETURN:
            ready_capital += cost; counts["ready_to_return"] += 1
        else:
            in_flight_capital += cost
            if state == RuntimeState.NEAR_RETURN: counts["near_return"] += 1
            else: counts["in_flight"] += 1
        quote = cache.get(voyage.symbol)
        quote_status = (
            QuoteStatus.FRESH
            if quote is not None and not market_open
            else cache.status(quote, now=now)
        )
        display_name = quote.name if quote and quote.name != voyage.symbol else voyage.security.name
        net_return = monitor.last_return_rate if monitor else None
        distance = None
        progress = Decimal("0")
        if net_return is not None:
            distance = max(voyage.target_return - net_return, Decimal("0"))
            progress = min(max(net_return / voyage.target_return, Decimal("0")), Decimal("1"))

        if quote_status != QuoteStatus.FRESH or net_return is None:
            visual_state = "WAITING_QUOTE"
        elif net_return < 0:
            visual_state = "PARKED_NEGATIVE"
        elif progress >= Decimal("1"):
            visual_state = "READY"
        elif progress >= Decimal("0.8"):
            visual_state = "APPROACHING"
        else:
            visual_state = "FLYING"

        item = {
            "id": voyage.id,
            "voyage_no": voyage.voyage_no,
            "symbol": voyage.symbol,
            "name": display_name,
            "remaining_quantity": remaining,
            "capital_amount": cost,
            "net_return": net_return,
            "target_return": voyage.target_return,
            "distance_to_target": distance,
            "progress": progress,
            "progress_percent": progress * Decimal("100"),
            "monitor_price": monitor.last_price if monitor else None,
            "runtime_state": state,
            "visual_state": visual_state,
            "quote_status": quote_status,
            "quote_time": quote.quote_time if quote else (monitor.last_quote_time if monitor else None),
            "entry_time": voyage.entry_time,
            "sellable_at": voyage.sellable_at,
        }
        routes.append(item)

        airport = airports.setdefault(
            voyage.symbol,
            {
                "symbol": voyage.symbol,
                "name": display_name,
                "flight_count": 0,
                "negative_count": 0,
                "waiting_count": 0,
                "alarm": False,
                "status": "ACTIVE",
            },
        )
        airport["flight_count"] += 1
        if visual_state == "PARKED_NEGATIVE":
            airport["negative_count"] += 1
            airport["alarm"] = True
        if visual_state == "WAITING_QUOTE":
            airport["waiting_count"] += 1

        if monitor and monitor.last_return_rate is not None:
            if state == RuntimeState.NEAR_RETURN: near.append(item)
            if state == RuntimeState.READY_TO_RETURN: ready.append(item)
    for airport in airports.values():
        if airport["waiting_count"] == airport["flight_count"]:
            airport["status"] = "WAITING"
        elif airport["alarm"]:
            airport["status"] = "ALERT"
    available = max(pool.total_capital - in_flight_capital - ready_capital, Decimal("0"))
    route_statuses = [route["quote_status"] for route in routes]
    quote_status = (
        QuoteStatus.FRESH
        if route_statuses and all(status == QuoteStatus.FRESH for status in route_statuses)
        else QuoteStatus.STALE
        if route_statuses
        else QuoteStatus.UNAVAILABLE
    )
    return success({
        "market": {"status": MarketStatus.OPEN if market_open else MarketStatus.CLOSED, "quote_status": quote_status, "updated_at": max((route["quote_time"] for route in routes if route["quote_time"] is not None), default=None)},
        "capital": {"total": pool.total_capital, "in_flight": in_flight_capital, "available": available, "ready_to_return": ready_capital},
        "counts": counts,
        "airports": sorted(airports.values(), key=lambda item: item["symbol"]),
        "routes": sorted(routes, key=lambda item: (item["symbol"], item["voyage_no"])),
        "near_returns": sorted(near, key=lambda x: x["distance_to_target"]),
        "ready_returns": ready,
    })
