from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.enums import SettlementMode

try:
    import pandas_market_calendars as mcal
except ImportError:  # pragma: no cover - exercised by monkeypatch in unit tests
    mcal = None  # type: ignore[assignment]

try:
    import exchange_calendars as exchange_mcal
    import pandas as pd
except ImportError:  # pragma: no cover - final fallback covers broken installs
    exchange_mcal = None  # type: ignore[assignment]
    pd = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
FALLBACK_MARKET_OPEN = time(9, 30)
FALLBACK_BREAK_START = time(11, 30)
FALLBACK_BREAK_END = time(13, 0)
FALLBACK_MARKET_CLOSE = time(15, 0)


class TradingCalendar:
    """Shanghai Stock Exchange trading sessions in Asia/Shanghai.

    SSE data from pandas-market-calendars is always preferred.  The weekday
    fallback is activated only when that dependency cannot be loaded or stops
    serving schedules. The first fallback is exchange-calendars' XSHG calendar;
    weekday/session rules are only the final degraded mode if both calendar
    dependencies are unavailable. An empty schedule is a real exchange holiday
    and is never mistaken for a dependency failure.

    ``trading_days_between`` excludes the starting date and includes the ending
    date.  This matches voyage duration semantics: Tuesday through Friday is
    three elapsed trading days (Wednesday, Thursday, Friday).
    """

    def __init__(self, calendar_name: str = "SSE") -> None:
        self.timezone = SHANGHAI_TZ
        self.calendar_name = calendar_name
        self._calendar: Any | None = None
        self._backend = "weekday"
        self._fallback_reason: str | None = None

        if mcal is None:
            self._activate_fallback("pandas_market_calendars is not installed")
            return
        try:
            self._calendar = mcal.get_calendar(calendar_name)
            self._backend = "pandas_market_calendars"
        except Exception as exc:  # dependency/calendar registry unavailable
            self._activate_fallback(str(exc))

    @property
    def using_fallback(self) -> bool:
        return self._backend != "pandas_market_calendars"

    def is_trading_day(self, value: date | datetime) -> bool:
        day = self._local_date(value)
        schedule = self._schedule(day, day)
        if schedule is None:
            return self._is_fallback_trading_day(day)
        return not schedule.empty

    def next_trading_day(self, value: date | datetime) -> date:
        """Return the first trading date strictly after ``value``."""

        start = self._local_date(value) + timedelta(days=1)
        for horizon in (14, 45, 370):
            end = start + timedelta(days=horizon)
            dates = self._trading_dates(start, end)
            if dates:
                return dates[0]
        raise RuntimeError(f"no SSE trading day found after {start.isoformat()}")

    def trading_days_between(
        self,
        start: date | datetime,
        end: date | datetime,
    ) -> int:
        """Count trading days in ``(start, end]`` using Shanghai dates."""

        start_day = self._local_date(start)
        end_day = self._local_date(end)
        if end_day <= start_day:
            return 0
        return len(self._trading_dates(start_day + timedelta(days=1), end_day))

    def is_market_open(self, value: datetime) -> bool:
        local_now = self._local_datetime(value)
        session = self._market_session(local_now.date())
        if session is None:
            return False
        market_open, break_start, break_end, market_close = session
        if not market_open <= local_now < market_close:
            return False
        if break_start is not None and break_end is not None:
            return not break_start <= local_now < break_end
        return True

    def calculate_sellable_at(
        self,
        entry_time: datetime,
        settlement_mode: SettlementMode | str,
    ) -> datetime:
        """Calculate the earliest sellable instant for a new voyage.

        T0 keeps the (Shanghai-normalized) entry instant. T1 starts at the next
        SSE session open. V1 has no custom-day field, so CUSTOM deliberately uses
        the conservative T1 rule.
        """

        local_entry = self._local_datetime(entry_time)
        mode = SettlementMode(settlement_mode)
        if mode == SettlementMode.T0:
            return local_entry

        sellable_day = self.next_trading_day(local_entry)
        session = self._market_session(sellable_day)
        if session is None:  # defensive: next_trading_day already validated it
            raise RuntimeError(
                f"unable to resolve market open for {sellable_day.isoformat()}"
            )
        return session[0]

    def _schedule(self, start: date, end: date):
        if self._backend == "weekday" or self._calendar is None:
            return None
        try:
            if self._backend == "pandas_market_calendars":
                return self._calendar.schedule(
                    start_date=start,
                    end_date=end,
                    tz=self.timezone,
                )
            sessions = self._calendar.sessions_in_range(start, end)
            rows = [
                {
                    "market_open": self._calendar.session_open(session),
                    "break_start": self._calendar.session_break_start(session),
                    "break_end": self._calendar.session_break_end(session),
                    "market_close": self._calendar.session_close(session),
                }
                for session in sessions
            ]
            return pd.DataFrame(rows, index=sessions)
        except Exception as exc:  # the dependency became unusable at runtime
            if self._backend == "pandas_market_calendars":
                self._activate_fallback(str(exc))
                return self._schedule(start, end)
            self._activate_weekday_fallback(str(exc))
            return None

    def _trading_dates(self, start: date, end: date) -> list[date]:
        schedule = self._schedule(start, end)
        if schedule is None:
            days: list[date] = []
            cursor = start
            while cursor <= end:
                if self._is_fallback_trading_day(cursor):
                    days.append(cursor)
                cursor += timedelta(days=1)
            return days
        return [timestamp.date() for timestamp in schedule.index]

    def _market_session(
        self,
        day: date,
    ) -> tuple[datetime, datetime | None, datetime | None, datetime] | None:
        schedule = self._schedule(day, day)
        if schedule is None:
            if not self._is_fallback_trading_day(day):
                return None
            return (
                datetime.combine(day, FALLBACK_MARKET_OPEN, self.timezone),
                datetime.combine(day, FALLBACK_BREAK_START, self.timezone),
                datetime.combine(day, FALLBACK_BREAK_END, self.timezone),
                datetime.combine(day, FALLBACK_MARKET_CLOSE, self.timezone),
            )
        if schedule.empty:
            return None

        row = schedule.iloc[0]
        market_open = self._timestamp_to_local_datetime(row["market_open"])
        market_close = self._timestamp_to_local_datetime(row["market_close"])
        break_start = self._optional_timestamp(row.get("break_start"))
        break_end = self._optional_timestamp(row.get("break_end"))
        return market_open, break_start, break_end, market_close

    def _activate_fallback(self, reason: str) -> None:
        self._fallback_reason = reason
        self._calendar = None
        if exchange_mcal is not None and pd is not None:
            try:
                self._calendar = exchange_mcal.get_calendar("XSHG")
                self._backend = "exchange_calendars"
                logger.warning(
                    "SSE calendar unavailable; using XSHG calendar fallback: %s",
                    reason,
                )
                return
            except Exception as exc:
                reason = f"{reason}; XSHG fallback unavailable: {exc}"
        self._activate_weekday_fallback(reason)

    def _activate_weekday_fallback(self, reason: str) -> None:
        logger.warning(
            "Exchange calendars unavailable; using weekday/session fallback: %s",
            reason,
        )
        self._fallback_reason = reason
        self._calendar = None
        self._backend = "weekday"

    @staticmethod
    def _is_fallback_trading_day(day: date) -> bool:
        return day.weekday() < 5

    def _local_date(self, value: date | datetime) -> date:
        if isinstance(value, datetime):
            return self._local_datetime(value).date()
        return value

    def _local_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=self.timezone)
        return value.astimezone(self.timezone)

    def _timestamp_to_local_datetime(self, value: Any) -> datetime:
        converted = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if not isinstance(converted, datetime):
            raise RuntimeError(f"invalid SSE schedule timestamp: {value!r}")
        return self._local_datetime(converted)

    def _optional_timestamp(self, value: Any) -> datetime | None:
        if value is None or type(value).__name__ == "NaTType":
            return None
        return self._timestamp_to_local_datetime(value)
