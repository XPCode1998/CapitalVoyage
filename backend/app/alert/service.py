from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alert.models import AlertEvent
from app.core.enums import AlertEventType, RuntimeState
from app.core.time import now_shanghai
from app.notification.base import Notifier
from app.return_engine.monitor import MonitorEvaluation, MonitorState


logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, session: Session, notifier: Notifier, *, cooldown_minutes: int = 30):
        self.session = session
        self.notifier = notifier
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def process(self, evaluation: MonitorEvaluation, *, now: datetime | None = None) -> list[AlertEvent]:
        event_types = self._transitions(evaluation.previous_state, evaluation.state)
        if not event_types:
            return []
        observed = now or now_shanghai()
        monitor = self.session.get(MonitorState, evaluation.voyage_id)
        events = [AlertEvent(
            voyage_id=evaluation.voyage_id, event_type=event_type.value,
            from_state=evaluation.previous_state.value if evaluation.previous_state else None,
            to_state=evaluation.state.value, message=f"航次 {evaluation.voyage_id}: {event_type.value}", created_at=observed,
        ) for event_type in event_types]
        self.session.add_all(events)
        allowed = monitor is None or monitor.last_notification_at is None or observed - monitor.last_notification_at >= self.cooldown
        if allowed:
            self.session.flush()
            # A target/ready/lost transition is more actionable than a simultaneous
            # quote recovery; persist both but send only the highest-priority event.
            priority = {AlertEventType.READY_TO_RETURN.value: 6, AlertEventType.TARGET_REACHED.value: 5, AlertEventType.TARGET_LOST.value: 4, AlertEventType.NEAR_RETURN_ENTERED.value: 3, AlertEventType.QUOTE_STALE.value: 2, AlertEventType.QUOTE_RECOVERED.value: 1}
            event = max(events, key=lambda item: priority.get(item.event_type, 0))
            try:
                self.notifier.send(event); event.notified_at = observed
                if monitor is not None: monitor.last_notification_at = observed
            except Exception:
                logger.exception("notification delivery failed for alert %s", event.id)
        self.session.flush()
        return events

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
        monitor = self.session.get(MonitorState, voyage_id)
        allowed = monitor is None or monitor.last_notification_at is None or observed - monitor.last_notification_at >= self.cooldown
        if allowed:
            try:
                self.notifier.send(event); event.notified_at = observed
                if monitor is not None: monitor.last_notification_at = observed
            except Exception:
                logger.exception("notification delivery failed for long-voyage alert %s", event.id)
        return event
