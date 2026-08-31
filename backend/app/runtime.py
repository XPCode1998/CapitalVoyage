from __future__ import annotations

from decimal import Decimal

from app.alert.service import AlertService
from app.calendar.service import TradingCalendar
from app.db.session import SessionLocal
from app.market.akshare_provider import AkshareETFMarketProvider
from app.market.cache import QuoteCache
from app.market.poller import MarketPoller
from app.notification.console import ConsoleNotifier
from app.notification.base import NullNotifier
from app.notification.feishu import FeishuNotifier
from app.notification.ntfy import NtfyNotifier
from app.return_engine.engine import ReturnEngine
from app.return_engine.fee import FeeCalculator
from app.return_engine.monitor import MonitorService
from app.settings.service import SettingsService
from app.core.enums import VoyageStatus
from app.core.time import now_shanghai
from app.voyage.repository import VoyageRepository


class RuntimeContainer:
    def __init__(self) -> None:
        with SessionLocal() as session:
            settings = SettingsService(session).get()
            stale = settings.market_quote_stale_seconds
            interval = settings.market_poll_interval_seconds
        self.quote_cache = QuoteCache(stale)
        self.provider = AkshareETFMarketProvider()
        self.poller = MarketPoller(self.provider, self.quote_cache, normal_interval_seconds=interval)

    def evaluate_monitors(self) -> None:
        with SessionLocal() as session:
            settings = SettingsService(session).get()
            engine = ReturnEngine(
                FeeCalculator(SettingsService(session).fee_config()),
                near_return_buffer=settings.near_return_buffer,
            )
            monitor = MonitorService(session, self.quote_cache, engine, price_mode=settings.return_price_mode)
            evaluations = monitor.evaluate_all(commit=False)
            notifier = self._notifier(settings.notification_provider, settings.notification_webhook_url)
            alert = AlertService(session, notifier, cooldown_minutes=settings.alert_cooldown_minutes)
            for evaluation in evaluations:
                alert.process(evaluation)
            calendar = TradingCalendar()
            observed = now_shanghai()
            for voyage in VoyageRepository(session).list(status=VoyageStatus.OPEN):
                alert.process_long_voyage(voyage.id, calendar.trading_days_between(voyage.entry_time, observed), settings.long_voyage_days, now=observed)
            session.commit()

    @staticmethod
    def _notifier(provider: str, url: str):
        if provider == "feishu" and url:
            return FeishuNotifier(url)
        if provider == "ntfy" and url:
            return NtfyNotifier(url)
        if provider == "none":
            return NullNotifier()
        return ConsoleNotifier()
