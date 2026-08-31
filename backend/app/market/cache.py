from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from threading import RLock

from app.core.enums import QuoteStatus
from app.core.time import now_shanghai
from app.market.models import Quote


class QuoteCache:
    def __init__(self, stale_after_seconds: int = 30) -> None:
        if isinstance(stale_after_seconds, bool) or not isinstance(
            stale_after_seconds, int
        ):
            raise TypeError("stale_after_seconds must be an int")
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self.stale_after_seconds = stale_after_seconds
        self._quotes: dict[str, Quote] = {}
        self._lock = RLock()

    def set(self, quote: Quote) -> None:
        if not isinstance(quote, Quote):
            raise TypeError("quote must be a Quote")
        with self._lock:
            self._quotes[quote.symbol] = quote

    def set_many(
        self,
        quotes: Mapping[str, Quote] | Iterable[Quote],
    ) -> None:
        values = quotes.values() if isinstance(quotes, Mapping) else quotes
        staged = list(values)
        if any(not isinstance(quote, Quote) for quote in staged):
            raise TypeError("all cached values must be Quote instances")
        with self._lock:
            self._quotes.update({quote.symbol: quote for quote in staged})

    def get(self, symbol: str) -> Quote | None:
        with self._lock:
            return self._quotes.get(symbol)

    def get_many(self, symbols: set[str]) -> dict[str, Quote]:
        with self._lock:
            return {
                symbol: quote
                for symbol in symbols
                if (quote := self._quotes.get(symbol)) is not None
            }

    def snapshot(self) -> dict[str, Quote]:
        with self._lock:
            return dict(self._quotes)

    def clear(self) -> None:
        with self._lock:
            self._quotes.clear()

    def is_fresh(
        self,
        quote_or_symbol: Quote | str,
        *,
        now: datetime | None = None,
    ) -> bool:
        quote = (
            quote_or_symbol
            if isinstance(quote_or_symbol, Quote)
            else self.get(quote_or_symbol)
        )
        if quote is None:
            return False
        reference = now or now_shanghai()
        self._require_aware(reference)
        age = reference.astimezone(timezone.utc) - quote.quote_time.astimezone(
            timezone.utc
        )
        # A materially future-dated quote is not trustworthy. Five seconds allows
        # harmless source/server clock skew without letting a bad timestamp remain
        # fresh indefinitely.
        if age < timedelta(seconds=-5):
            return False
        return age <= timedelta(seconds=self.stale_after_seconds)

    def status(
        self,
        quote_or_symbol: Quote | str,
        *,
        now: datetime | None = None,
    ) -> QuoteStatus:
        quote = (
            quote_or_symbol
            if isinstance(quote_or_symbol, Quote)
            else self.get(quote_or_symbol)
        )
        if quote is None:
            return QuoteStatus.UNAVAILABLE
        if self.is_fresh(quote, now=now):
            return QuoteStatus.FRESH
        return QuoteStatus.STALE

    def is_usable(
        self,
        quote_or_symbol: Quote | str,
        *,
        market_open: bool,
        now: datetime | None = None,
    ) -> bool:
        """Allow the latest valid close outside trading hours.

        Intraday decisions still require a fresh quote. When the exchange is
        closed, an existing cached quote is the latest available close and does
        not expire merely because wall-clock time continues to pass.
        """

        quote = (
            quote_or_symbol
            if isinstance(quote_or_symbol, Quote)
            else self.get(quote_or_symbol)
        )
        if quote is None:
            return False
        return not market_open or self.is_fresh(quote, now=now)

    @staticmethod
    def _require_aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("freshness reference time must be timezone-aware")
