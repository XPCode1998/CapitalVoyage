from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import VoyageStatus
from app.db.session import SessionLocal
from app.market.base import MarketProvider
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.voyage.models import Voyage


logger = logging.getLogger(__name__)

DEFAULT_BACKOFF_SECONDS = (15, 30, 60, 120, 300)
SessionFactory = Callable[[], Session]
QuotesCallback = Callable[[Mapping[str, Quote]], object]


@dataclass(frozen=True, slots=True)
class PollResult:
    symbols: frozenset[str]
    quotes: dict[str, Quote]
    success: bool
    next_interval_seconds: int
    error: Exception | None = None
    callback_error: Exception | None = None


class MarketPoller:
    """Fetch quotes for distinct symbols used by OPEN voyages.

    Scheduling is deliberately outside this class. ``poll_once`` performs one
    unit of work and exposes ``next_interval_seconds`` for the later APScheduler
    lifecycle. Provider/database failures never clear QuoteCache, allowing old
    quotes to age naturally into STALE state.
    """

    def __init__(
        self,
        provider: MarketProvider,
        cache: QuoteCache,
        *,
        session_factory: SessionFactory = SessionLocal,
        on_quotes: QuotesCallback | None = None,
        normal_interval_seconds: int = 15,
        backoff_seconds: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        if normal_interval_seconds <= 0:
            raise ValueError("normal_interval_seconds must be positive")
        if not backoff_seconds or any(delay <= 0 for delay in backoff_seconds):
            raise ValueError("backoff_seconds must contain positive delays")

        self.provider = provider
        self.cache = cache
        self.session_factory = session_factory
        self.on_quotes = on_quotes
        self.normal_interval_seconds = normal_interval_seconds
        self.backoff_seconds = backoff_seconds

        self.consecutive_failures = 0
        self.next_interval_seconds = normal_interval_seconds
        self.last_error: Exception | None = None
        self.last_callback_error: Exception | None = None

    def poll_once(self) -> PollResult:
        symbols: frozenset[str] = frozenset()
        try:
            symbols = frozenset(self._load_open_symbols())
            if not symbols:
                self._mark_success()
                return PollResult(
                    symbols=symbols,
                    quotes={},
                    success=True,
                    next_interval_seconds=self.next_interval_seconds,
                )

            quotes = dict(self.provider.get_quotes(set(symbols)))
            self.cache.set_many(quotes)
        except Exception as exc:
            self._mark_failure(exc)
            logger.warning(
                "market poll failed; retaining cached quotes and retrying in %ss",
                self.next_interval_seconds,
                exc_info=True,
            )
            return PollResult(
                symbols=symbols,
                quotes={},
                success=False,
                next_interval_seconds=self.next_interval_seconds,
                error=exc,
            )

        self._mark_success()
        callback_error: Exception | None = None
        if self.on_quotes is not None:
            try:
                self.on_quotes(dict(quotes))
            except Exception as exc:
                callback_error = exc
                self.last_callback_error = exc
                logger.exception("market on_quotes callback failed")

        return PollResult(
            symbols=symbols,
            quotes=quotes,
            success=True,
            next_interval_seconds=self.next_interval_seconds,
            callback_error=callback_error,
        )

    def _load_open_symbols(self) -> set[str]:
        with self.session_factory() as session:
            values = session.scalars(
                select(Voyage.symbol)
                .where(Voyage.status == VoyageStatus.OPEN)
                .distinct()
            ).all()
        return {symbol.strip().upper() for symbol in values if symbol}

    def _mark_success(self) -> None:
        self.consecutive_failures = 0
        self.next_interval_seconds = self.normal_interval_seconds
        self.last_error = None
        self.last_callback_error = None

    def _mark_failure(self, error: Exception) -> None:
        self.consecutive_failures += 1
        index = min(self.consecutive_failures - 1, len(self.backoff_seconds) - 1)
        self.next_interval_seconds = self.backoff_seconds[index]
        self.last_error = error
        self.last_callback_error = None
