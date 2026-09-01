from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert.models import AlertEvent
from app.calendar.service import TradingCalendar
from app.core.enums import AlertEventType, RuntimeState
from app.core.time import now_shanghai
from app.notification.base import Notifier
from app.notification.payload import AlertNotification
from app.return_engine.models import RuntimeResult
from app.return_engine.monitor import MonitorEvaluation, MonitorState
from app.voyage.models import Voyage


logger = logging.getLogger(__name__)


class AlertService:
    NOTIFICATION_INTERVALS = {
        RuntimeState.NEAR_RETURN: (AlertEventType.NEAR_RETURN_ENTERED, timedelta(minutes=5)),
        RuntimeState.READY_TO_RETURN: (AlertEventType.READY_TO_RETURN, timedelta(minutes=1)),
    }

    def __init__(
        self,
        session: Session,
        notifier: Notifier,
        trading_calendar: TradingCalendar | None = None,
    ):
        self.session = session
        self.notifier = notifier
        self.trading_calendar = trading_calendar or TradingCalendar()

    def process(self, evaluation: MonitorEvaluation, *, now: datetime | None = None) -> list[AlertEvent]:
        event_types = self._transitions(evaluation.previous_state, evaluation.state)
        observed = now or now_shanghai()
        monitor = self.session.get(MonitorState, evaluation.voyage_id)
        events = [AlertEvent(
            voyage_id=evaluation.voyage_id, event_type=event_type.value,
            from_state=evaluation.previous_state.value if evaluation.previous_state else None,
            to_state=evaluation.state.value, message=f"航次 {evaluation.voyage_id}: {event_type.value}", created_at=observed,
        ) for event_type in event_types]
        if events:
            self.session.add_all(events)
        # Alert events are retained outside the session for auditability, but
        # outbound notifications must never disturb users while the SSE market
        # is closed (including the midday break and exchange holidays).
        notification = None
        if self.trading_calendar.is_market_open(observed):
            notification = self._notification_for(evaluation.voyage_id, evaluation.state, events, observed)
        else:
            logger.debug(
                "notification suppressed outside market session: voyage=%s state=%s",
                evaluation.voyage_id,
                evaluation.state.value,
            )
        if notification is not None:
            self.session.flush()
            try:
                outbound = (
                    self._notification_payload(notification, evaluation.runtime)
                    if evaluation.runtime is not None
                    else notification
                )
                self.notifier.send(outbound)
                notification.notified_at = observed
                if monitor is not None:
                    monitor.last_notification_at = observed
            except Exception:
                logger.exception("notification delivery failed for alert %s", notification.id)
        self.session.flush()
        return events

    def _notification_for(
        self,
        voyage_id: int,
        state: RuntimeState,
        events: list[AlertEvent],
        observed: datetime,
    ) -> AlertEvent | None:
        """Return the only event types that may leave the application.

        A new state entry is sent immediately; remaining in the same state emits
        another alert only after that state type's own interval has elapsed.
        """
        schedule = self.NOTIFICATION_INTERVALS.get(state)
        if schedule is None:
            return None
        event_type, interval = schedule
        entered = next((event for event in events if event.event_type == event_type.value), None)
        if entered is not None:
            return entered
        latest = self.session.scalar(
            select(AlertEvent.notified_at)
            .where(
                AlertEvent.voyage_id == voyage_id,
                AlertEvent.event_type == event_type.value,
                AlertEvent.notified_at.is_not(None),
            )
            .order_by(AlertEvent.notified_at.desc())
            .limit(1)
        )
        if latest is not None and observed - latest < interval:
            return None
        periodic = AlertEvent(
            voyage_id=voyage_id,
            event_type=event_type.value,
            from_state=state.value,
            to_state=state.value,
            message=f"航次 {voyage_id}: {event_type.value}",
            created_at=observed,
        )
        self.session.add(periodic)
        events.append(periodic)
        return periodic

    def _notification_payload(
        self,
        event: AlertEvent,
        runtime: RuntimeResult | None,
    ) -> AlertNotification:
        """Build a rich outbound payload without storing volatile quotes."""
        if runtime is None:
            raise ValueError("notifiable return alert requires runtime data")
        voyage = self.session.get(Voyage, event.voyage_id)
        if voyage is None:  # defensive; the event has a foreign-key reference
            raise LookupError(f"voyage {event.voyage_id} does not exist")
        monitor = self.session.get(MonitorState, voyage.id)
        ready = event.event_type == AlertEventType.READY_TO_RETURN.value
        delta = runtime.net_return - runtime.target_return
        if ready:
            message = (
                f"航次 {voyage.voyage_no}（{voyage.symbol} {voyage.security.name}）可返航："
                f"当前净收益 {self._format_percent(runtime.net_return)}，"
                f"超过目标 {self._format_points(delta)}。"
            )
            interval_minutes = 1
        else:
            message = (
                f"航次 {voyage.voyage_no}（{voyage.symbol} {voyage.security.name}）接近返航："
                f"当前净收益 {self._format_percent(runtime.net_return)}，"
                f"距目标还差 {self._format_points(runtime.distance_to_target)}。"
            )
            interval_minutes = 5
        return AlertNotification(
            event_type=event.event_type,
            message=message,
            voyage_no=voyage.voyage_no,
            symbol=voyage.symbol,
            security_name=voyage.security.name,
            slot_no=voyage.slot.slot_no,
            net_return=runtime.net_return,
            target_return=runtime.target_return,
            distance_to_target=runtime.distance_to_target,
            monitor_price=runtime.monitor_price,
            target_price=runtime.target_price,
            remaining_quantity=runtime.remaining_quantity,
            quote_time=monitor.last_quote_time if monitor else None,
            interval_minutes=interval_minutes,
        )

    @staticmethod
    def _format_percent(value) -> str:
        return f"{value * 100:+.2f}%"

    @staticmethod
    def _format_points(value) -> str:
        return f"{value * 100:.2f}pp"

    @staticmethod
    def _transitions(old: RuntimeState | None, new: RuntimeState) -> list[AlertEventType]:
        if old == new:
            return []
        events: list[AlertEventType] = []
        if new == RuntimeState.QUOTE_STALE:
            return [AlertEventType.QUOTE_STALE]
        if old == RuntimeState.QUOTE_STALE: events.append(AlertEventType.QUOTE_RECOVERED)
        if old in {RuntimeState.TARGET_REACHED_NOT_SELLABLE, RuntimeState.READY_TO_RETURN} and new not in {RuntimeState.TARGET_REACHED_NOT_SELLABLE, RuntimeState.READY_TO_RETURN}:
            events.append(AlertEventType.TARGET_LOST)
        if new == RuntimeState.NEAR_RETURN:
            events.append(AlertEventType.NEAR_RETURN_ENTERED)
        if new == RuntimeState.TARGET_REACHED_NOT_SELLABLE:
            events.append(AlertEventType.TARGET_REACHED)
        if new == RuntimeState.READY_TO_RETURN:
            events.append(AlertEventType.READY_TO_RETURN)
        return events

    def list(self, limit: int = 100) -> list[AlertEvent]:
        return list(self.session.scalars(select(AlertEvent).order_by(AlertEvent.id.desc()).limit(limit)).all())

    def process_long_voyage(self, voyage_id: int, trading_days: int, threshold: int, *, now: datetime | None = None) -> AlertEvent | None:
        if trading_days < threshold:
            return None
        existing = self.session.scalar(select(AlertEvent.id).where(AlertEvent.voyage_id == voyage_id, AlertEvent.event_type == AlertEventType.LONG_VOYAGE.value).limit(1))
        if existing is not None:
            return None
        observed = now or now_shanghai()
        event = AlertEvent(voyage_id=voyage_id, event_type=AlertEventType.LONG_VOYAGE.value, from_state=None, to_state="LONG_VOYAGE", message=f"航次 {voyage_id} 已在航 {trading_days} 个交易日", created_at=observed)
        self.session.add(event); self.session.flush()
        return event
