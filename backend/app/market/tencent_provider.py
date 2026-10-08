from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.core.time import now_shanghai
from app.market.base import MarketProvider
from app.market.models import Quote


SOURCE = "tencent"
QUOTE_URL = "https://qt.gtimg.cn/q="
REQUEST_TIMEOUT_SECONDS = 8.0
_RECORD_PATTERN = re.compile(r'v_[^=]+="(?P<values>[^"]*)";')


class TencentETFMarketProvider(MarketProvider):
    """Fetch only the requested ETF quotes from Tencent Finance's public feed.

    Tencent emits one tilde-delimited record per symbol. The full record includes
    latest price, best bid, best ask and a second-resolution source timestamp,
    which are the fields needed by the return monitor.
    """

    def __init__(
        self,
        *,
        now_factory: Callable[[], datetime] = now_shanghai,
        fetcher: Callable[[set[str]], str | bytes] | None = None,
    ) -> None:
        self._now_factory = now_factory
        self._fetcher = fetcher

    def get_quotes(self, symbols: set[str]) -> dict[str, Quote]:
        requested = {_normalize_symbol(symbol) for symbol in symbols if str(symbol).strip()}
        if not requested:
            return {}

        received_at = self._now_factory()
        _require_aware(received_at, "received_at")
        payload = (self._fetcher or self._request)(requested)
        text = payload.decode("gb18030", errors="replace") if isinstance(payload, bytes) else payload
        if not isinstance(text, str):
            raise TypeError("Tencent quote fetcher must return text or bytes")

        quotes: dict[str, Quote] = {}
        for match in _RECORD_PATTERN.finditer(text):
            fields = match.group("values").split("~")
            if len(fields) <= 30:
                continue
            symbol = _normalize_symbol(fields[2])
            if symbol not in requested:
                continue
            last_price = _positive_decimal(fields[3])
            if last_price is None:
                continue
            quote_time = _parse_time(fields[30])
            if quote_time is None:
                continue
            quotes[symbol] = Quote(
                symbol=symbol,
                name=fields[1].strip() or symbol,
                last_price=last_price,
                bid1=_nonnegative_decimal(fields[9]),
                ask1=_nonnegative_decimal(fields[19]),
                quote_time=quote_time,
                received_at=received_at,
                source=SOURCE,
            )
        return quotes

    @staticmethod
    def _request(symbols: set[str]) -> bytes:
        codes = ",".join(_market_code(symbol) for symbol in sorted(symbols))
        response = httpx.get(
            f"{QUOTE_URL}{codes}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; CapitalVoyage/1.0)"},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.content


def _market_code(symbol: str) -> str:
    # Shanghai ETFs/funds are commonly 5xxxxx/6xxxxx; Shenzhen ETFs are 1xxxxx.
    return f"{'sh' if symbol.startswith(('5', '6', '9')) else 'sz'}{symbol}"


def _normalize_symbol(value: object) -> str:
    text = str(value).strip().upper()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", maxsplit=1)[0]
    return text


def _positive_decimal(value: object) -> Decimal | None:
    result = _decimal(value)
    return result if result is not None and result > 0 else None


def _nonnegative_decimal(value: object) -> Decimal | None:
    result = _decimal(value)
    return result if result is not None and result >= 0 else None


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _parse_time(value: object) -> datetime | None:
    text = str(value).strip()
    if not re.fullmatch(r"\d{14}", text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=now_shanghai().tzinfo)
    except ValueError:
        return None


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
