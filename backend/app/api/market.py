from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.common import success
from app.calendar.service import TradingCalendar
from app.core.enums import MarketStatus, QuoteStatus
from app.core.time import now_shanghai
from app.db.session import get_db
from app.security.service import SecurityService


router = APIRouter(prefix="/api", tags=["Market"])


@router.get("/market/status")
def market_status(request: Request):
    now = now_shanghai()
    cache = request.app.state.runtime.quote_cache
    quotes = cache.snapshot()
    market_open = TradingCalendar().is_market_open(now)
    statuses = [cache.status(q, now=now) for q in quotes.values()]
    quote_status = QuoteStatus.FRESH if quotes and not market_open else (QuoteStatus.FRESH if QuoteStatus.FRESH in statuses else (QuoteStatus.STALE if statuses else QuoteStatus.UNAVAILABLE))
    return success({
        "status": MarketStatus.OPEN if market_open else MarketStatus.CLOSED,
        "quote_status": quote_status,
        "updated_at": max((q.quote_time for q in quotes.values()), default=None),
        "provider": "akshare",
        "last_error": str(request.app.state.runtime.poller.last_error) if request.app.state.runtime.poller.last_error else None,
    })


@router.get("/securities/search")
def search_securities(request: Request, q: str = Query(default=""), db: Session = Depends(get_db)):
    local = SecurityService(db).search(q, limit=20)
    data = [{"symbol": s.symbol, "name": s.name, "market": s.market, "settlement_mode": s.settlement_mode, "last_price": (request.app.state.runtime.quote_cache.get(s.symbol).last_price if request.app.state.runtime.quote_cache.get(s.symbol) else None)} for s in local]
    normalized = q.strip().upper()
    quote = request.app.state.runtime.quote_cache.get(normalized)
    if normalized.isdigit() and len(normalized) == 6 and quote is None:
        try:
            fetched = request.app.state.runtime.provider.get_quotes({normalized})
            request.app.state.runtime.quote_cache.set_many(fetched)
            quote = fetched.get(normalized)
        except Exception:
            quote = None
    if normalized and quote and all(item["symbol"] != normalized for item in data):
        data.insert(0, {"symbol": quote.symbol, "name": quote.name, "market": "CN", "settlement_mode": "T1", "last_price": quote.last_price})
    return success(data)
