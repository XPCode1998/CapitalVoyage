from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.core.enums import QuoteStatus, ReturnPriceMode
from app.market import AkshareETFMarketProvider, MarketProvider, Quote, QuoteCache


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _quote(
    *,
    quote_time: datetime,
    bid1: Decimal | None = Decimal("4.011"),
) -> Quote:
    return Quote(
        symbol="510300",
        name="沪深300ETF",
        last_price=Decimal("4.012"),
        bid1=bid1,
        ask1=Decimal("4.013"),
        quote_time=quote_time,
        received_at=quote_time,
        source="test",
    )


def test_quote_requires_decimal_prices_and_aware_times() -> None:
    aware = datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)

    with pytest.raises(TypeError, match="Decimal"):
        Quote(
            symbol="510300",
            name="沪深300ETF",
            last_price=4.012,  # type: ignore[arg-type]
            bid1=None,
            ask1=None,
            quote_time=aware,
            received_at=aware,
            source="test",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        _quote(quote_time=datetime(2026, 8, 28, 10, 0))


@pytest.mark.parametrize("bid1", [None, Decimal("0")])
def test_monitor_price_prefers_positive_bid1_otherwise_last(
    bid1: Decimal | None,
) -> None:
    quote_time = datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
    quote = _quote(quote_time=quote_time, bid1=bid1)

    assert quote.monitor_price == Decimal("4.012")
    assert quote.price_for(ReturnPriceMode.LAST) == Decimal("4.012")

    positive_bid = _quote(quote_time=quote_time, bid1=Decimal("4.011"))
    assert positive_bid.monitor_price == Decimal("4.011")


def test_market_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        MarketProvider()


def test_quote_cache_uses_quote_time_and_thirty_second_boundary() -> None:
    quote_time = datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
    cache = QuoteCache()
    cache.set_many({"510300": _quote(quote_time=quote_time)})

    assert cache.get("510300") is not None
    assert cache.is_fresh("510300", now=quote_time + timedelta(seconds=30))
    assert cache.status(
        "510300", now=quote_time + timedelta(seconds=30)
    ) == QuoteStatus.FRESH
    assert not cache.is_fresh("510300", now=quote_time + timedelta(seconds=31))
    assert cache.status(
        "510300", now=quote_time + timedelta(seconds=31)
    ) == QuoteStatus.STALE
    assert cache.status("missing", now=quote_time) == QuoteStatus.UNAVAILABLE


def test_akshare_provider_filters_full_chinese_table_and_handles_nan() -> None:
    received_at = datetime(2026, 8, 28, 10, 0, 10, tzinfo=SHANGHAI)
    frame = pd.DataFrame(
        [
            {
                "代码": "510300",
                "名称": "沪深300ETF",
                "最新价": 4.012,
                "买一": 4.011,
                "卖一": 4.013,
                "更新时间": pd.Timestamp("2026-08-28 10:00:08", tz=SHANGHAI),
            },
            {
                "代码": "512880",
                "名称": "证券ETF",
                "最新价": 1.234,
                "买一": float("nan"),
                "卖一": float("nan"),
                "更新时间": pd.Timestamp("2026-08-28 10:00:07", tz=SHANGHAI),
            },
            {
                "代码": "159915",
                "名称": "创业板ETF",
                "最新价": 2.345,
                "买一": 2.344,
                "卖一": 2.346,
                "更新时间": pd.Timestamp("2026-08-28 10:00:06", tz=SHANGHAI),
            },
        ]
    )
    calls = 0

    def fetcher() -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return frame

    provider = AkshareETFMarketProvider(
        now_factory=lambda: received_at,
        fetcher=fetcher,
    )

    quotes = provider.get_quotes({"510300", "512880"})

    assert calls == 1
    assert set(quotes) == {"510300", "512880"}
    assert quotes["510300"].last_price == Decimal("4.012")
    assert quotes["510300"].bid1 == Decimal("4.011")
    assert quotes["510300"].ask1 == Decimal("4.013")
    assert quotes["510300"].quote_time == datetime(
        2026, 8, 28, 10, 0, 8, tzinfo=SHANGHAI
    )
    assert quotes["512880"].bid1 is None
    assert quotes["512880"].ask1 is None
    assert all(isinstance(quote.last_price, Decimal) for quote in quotes.values())


def test_akshare_provider_supports_english_and_missing_optional_columns() -> None:
    received_at = datetime(2026, 8, 28, 10, 5, tzinfo=SHANGHAI)
    frame = pd.DataFrame(
        [
            {"symbol": 510300, "name": "CSI 300 ETF", "last_price": "4.012"},
            {"symbol": "512880", "name": None, "last_price": "--"},
        ]
    )
    provider = AkshareETFMarketProvider(
        now_factory=lambda: received_at,
        fetcher=lambda: frame,
    )

    quotes = provider.get_quotes({"510300", "512880"})

    assert set(quotes) == {"510300"}
    assert quotes["510300"].name == "CSI 300 ETF"
    assert quotes["510300"].bid1 is None
    assert quotes["510300"].ask1 is None
    assert quotes["510300"].quote_time == received_at


def test_missing_timestamp_on_weekend_uses_last_session_close_and_is_stale() -> None:
    saturday = datetime(2026, 8, 29, 10, 0, tzinfo=SHANGHAI)
    provider = AkshareETFMarketProvider(
        now_factory=lambda: saturday,
        fetcher=lambda: pd.DataFrame(
            [{"代码": "510300", "名称": "沪深300ETF", "最新价": "4.012"}]
        ),
    )

    quote = provider.get_quotes({"510300"})["510300"]

    assert quote.received_at == saturday
    assert quote.quote_time == datetime(2026, 8, 28, 15, 0, tzinfo=SHANGHAI)
    assert QuoteCache().status(quote, now=saturday) == QuoteStatus.STALE


def test_reliable_after_hours_source_time_is_preserved() -> None:
    after_close = datetime(2026, 8, 28, 18, 0, tzinfo=SHANGHAI)
    provider = AkshareETFMarketProvider(
        now_factory=lambda: after_close,
        fetcher=lambda: pd.DataFrame(
            [
                {
                    "code": "510300",
                    "last": "4.012",
                    "timestamp": "2026-08-28T18:00:00+08:00",
                }
            ]
        ),
    )

    quote = provider.get_quotes({"510300"})["510300"]

    assert quote.name == "510300"
    assert quote.quote_time == after_close
    assert QuoteCache().status(quote, now=after_close) == QuoteStatus.FRESH


def test_time_only_source_column_combines_with_data_date() -> None:
    received_at = datetime(2026, 8, 28, 10, 1, tzinfo=SHANGHAI)
    provider = AkshareETFMarketProvider(
        now_factory=lambda: received_at,
        fetcher=lambda: pd.DataFrame(
            [
                {
                    "code": "510300",
                    "price": "4.012",
                    "time": "10:00:59",
                    "trade_date": "2026-08-28",
                }
            ]
        ),
    )

    quote = provider.get_quotes({"510300"})["510300"]

    assert quote.quote_time == datetime(2026, 8, 28, 10, 0, 59, tzinfo=SHANGHAI)
