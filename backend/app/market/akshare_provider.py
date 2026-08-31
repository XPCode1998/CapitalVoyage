from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd
import pandas_market_calendars as mcal

from app.core.time import now_shanghai
from app.market.base import MarketProvider
from app.market.models import Quote


SHANGHAI = ZoneInfo("Asia/Shanghai")
SOURCE = "akshare"

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": ("代码", "证券代码", "基金代码", "symbol", "code", "ticker"),
    "name": ("名称", "证券简称", "基金简称", "name", "security_name"),
    "last_price": (
        "最新价",
        "最新价格",
        "last_price",
        "last",
        "price",
        "close",
    ),
    "bid1": ("买一", "买一价", "bid1", "bid_1", "bid_1_price", "best_bid"),
    "ask1": ("卖一", "卖一价", "ask1", "ask_1", "ask_1_price", "best_ask"),
    "quote_time": (
        "更新时间",
        "行情时间",
        "quote_time",
        "update_time",
        "updated_at",
        "timestamp",
        "time",
    ),
    "data_date": ("数据日期", "交易日期", "data_date", "trade_date", "date"),
}


class AkshareETFMarketProvider(MarketProvider):
    """Adapts AKShare's full ETF snapshot to strict domain Quote objects."""

    def __init__(
        self,
        *,
        now_factory: Callable[[], datetime] = now_shanghai,
        fetcher: Callable[[], Any] | None = None,
    ) -> None:
        self._now_factory = now_factory
        self._fetcher = fetcher
        self._calendar = mcal.get_calendar("XSHG")
        self._schedule_cache: dict[date, pd.DataFrame] = {}

    def get_quotes(self, symbols: set[str]) -> dict[str, Quote]:
        requested = {_normalize_symbol(symbol) for symbol in symbols if str(symbol).strip()}
        if not requested:
            return {}

        received_at = self._now_factory()
        _require_aware(received_at, "received_at")
        received_at = received_at.astimezone(SHANGHAI)
        frame = (self._fetcher or ak.fund_etf_spot_em)()
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("akshare fund_etf_spot_em must return a DataFrame")

        columns = _resolve_columns(frame.columns)
        if "symbol" not in columns or "last_price" not in columns:
            return {}

        session_reference = self._session_reference(received_at)
        quotes: dict[str, Quote] = {}
        for _index, row in frame.iterrows():
            symbol = _normalize_symbol(row.get(columns["symbol"]))
            if not symbol or symbol not in requested:
                continue

            last_price = _to_decimal(row.get(columns["last_price"]))
            if last_price is None or last_price <= 0:
                continue
            bid1 = _optional_nonnegative_price(row, columns.get("bid1"))
            ask1 = _optional_nonnegative_price(row, columns.get("ask1"))
            raw_name = row.get(columns["name"]) if "name" in columns else None
            name = _to_text(raw_name) or symbol

            raw_date = row.get(columns["data_date"]) if "data_date" in columns else None
            raw_time = (
                row.get(columns["quote_time"]) if "quote_time" in columns else None
            )
            quote_time = _parse_quote_time(raw_time, data_date=raw_date)
            if quote_time is None:
                quote_time = session_reference

            quote = Quote(
                symbol=symbol,
                name=name,
                last_price=last_price,
                bid1=bid1,
                ask1=ask1,
                quote_time=quote_time,
                received_at=received_at,
                source=SOURCE,
            )
            existing = quotes.get(symbol)
            if existing is None or quote.quote_time >= existing.quote_time:
                quotes[symbol] = quote

        return quotes

    def _session_reference(self, received_at: datetime) -> datetime:
        schedule = self._schedule(received_at.date())
        today_rows = schedule[schedule.index.date == received_at.date()]
        if not today_rows.empty:
            row = today_rows.iloc[0]
            market_open = _as_shanghai_datetime(row["market_open"])
            market_close = _as_shanghai_datetime(row["market_close"])
            break_start = _as_optional_shanghai_datetime(row.get("break_start"))
            break_end = _as_optional_shanghai_datetime(row.get("break_end"))

            in_morning = market_open <= received_at <= (break_start or market_close)
            in_afternoon = (
                break_end is not None and break_end <= received_at <= market_close
            )
            if in_morning or in_afternoon:
                return received_at
            if break_start is not None and break_end is not None:
                if break_start < received_at < break_end:
                    return break_start
            if received_at > market_close:
                return market_close

        completed_closes = [
            _as_shanghai_datetime(value)
            for value in schedule["market_close"]
            if _as_shanghai_datetime(value) <= received_at
        ]
        if completed_closes:
            return completed_closes[-1]

        # Defensive only: XSHG normally has a completed session in the 40-day
        # window. Staying old is safer than fabricating freshness if it does not.
        fallback_day = received_at.date() - timedelta(days=1)
        return datetime.combine(fallback_day, time(15), tzinfo=SHANGHAI)

    def _schedule(self, day: date) -> pd.DataFrame:
        cached = self._schedule_cache.get(day)
        if cached is not None:
            return cached
        schedule = self._calendar.schedule(
            start_date=day - timedelta(days=40),
            end_date=day,
        )
        self._schedule_cache = {day: schedule}
        return schedule


def _normalize_column(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def _resolve_columns(columns: Any) -> dict[str, object]:
    normalized = {_normalize_column(column): column for column in columns}
    result: dict[str, object] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            column = normalized.get(_normalize_column(alias))
            if column is not None:
                result[field] = column
                break
    return result


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool):
            return missing
        if hasattr(missing, "item"):
            return bool(missing.item())
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in {"", "-", "--", "nan", "none", "null", "n/a"}
    return False


def _to_text(value: object) -> str | None:
    if _is_missing(value):
        return None
    return str(value).strip()


def _normalize_symbol(value: object) -> str:
    text = _to_text(value)
    if text is None:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", maxsplit=1)[0]
    return text.upper()


def _to_decimal(value: object) -> Decimal | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not result.is_finite():
        return None
    return result


def _optional_nonnegative_price(
    row: Mapping[object, object],
    column: object | None,
) -> Decimal | None:
    if column is None:
        return None
    value = _to_decimal(row.get(column))
    if value is None or value < 0:
        return None
    return value


def _parse_quote_time(value: object, *, data_date: object = None) -> datetime | None:
    if _is_missing(value):
        return None

    parsed: pd.Timestamp
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        unit = "ms" if abs(numeric) >= 1_000_000_000_000 else "s"
        parsed = pd.Timestamp(numeric, unit=unit, tz="UTC")
    else:
        text_value = str(value).strip()
        if re.fullmatch(r"\d{10}|\d{13}", text_value):
            unit = "ms" if len(text_value) == 13 else "s"
            parsed = pd.Timestamp(int(text_value), unit=unit, tz="UTC")
        elif re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?", text_value):
            parsed_date = _parse_data_date(data_date)
            if parsed_date is None:
                return None
            parsed = pd.Timestamp(f"{parsed_date.isoformat()} {text_value}")
        else:
            try:
                parsed = pd.Timestamp(value)
            except (TypeError, ValueError, OverflowError):
                return None
            if parsed.hour == parsed.minute == parsed.second == parsed.microsecond == 0:
                # A date alone identifies a session, not a quote instant.
                return None

    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(SHANGHAI)
    else:
        parsed = parsed.tz_convert(SHANGHAI)
    result = parsed.to_pydatetime()
    _require_aware(result, "quote_time")
    return result


def _parse_data_date(value: object) -> date | None:
    if _is_missing(value):
        return None
    text_value = str(value).strip()
    if re.fullmatch(r"\d{8}", text_value):
        try:
            return datetime.strptime(text_value, "%Y%m%d").date()
        except ValueError:
            return None
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _as_shanghai_datetime(value: object) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(timezone.utc)
    return parsed.tz_convert(SHANGHAI).to_pydatetime()


def _as_optional_shanghai_datetime(value: object) -> datetime | None:
    if _is_missing(value):
        return None
    return _as_shanghai_datetime(value)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
