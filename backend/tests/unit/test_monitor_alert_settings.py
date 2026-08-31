from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.alert.models import AlertEvent
from app.alert.service import AlertService
from app.capital.service import CapitalService
from app.core.enums import AlertEventType, RuntimeState, SettlementMode, SlotStatus
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.notification.base import Notifier
from app.return_engine.engine import ReturnEngine
from app.return_engine.fee import FeeCalculator
from app.return_engine.models import FeeConfig
from app.return_engine.monitor import MonitorEvaluation, MonitorService, MonitorState
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.settings.schemas import SettingsUpdate
from app.settings.service import SettingsService
from app.voyage.schemas import VoyageCreate
from app.voyage.service import VoyageService


TZ = ZoneInfo("Asia/Shanghai")
ENTRY = datetime(2026, 8, 28, 10, 0, tzinfo=TZ)
NOW = datetime(2026, 8, 31, 10, 0, tzinfo=TZ)


def voyage(session, price="4.000"):
    SecurityService(session).create(SecurityCreate(symbol="510300", name="沪深300ETF", settlement_mode=SettlementMode.T1))
    slot = CapitalService(session).list_slots()[0]
    return VoyageService(session).create(VoyageCreate(slot_id=slot.id, symbol="510300", entry_time=ENTRY, entry_price=Decimal(price), entry_quantity=1000, entry_fee=Decimal("0"), target_return=Decimal("0.02"), sellable_at=NOW - timedelta(minutes=1)))


def quote(price: str, at: datetime = NOW):
    return Quote(symbol="510300", name="沪深300ETF", last_price=Decimal(price), bid1=Decimal(price), ask1=Decimal(price), quote_time=at, received_at=at, source="test")


def test_monitor_state_moves_near_ready_falls_back_and_stale_blocks_ready(initialized_db_session):
    v = voyage(initialized_db_session)
    cache = QuoteCache(30)
    engine = ReturnEngine(FeeCalculator(FeeConfig()), near_return_buffer=Decimal("0.002"))
    monitor = MonitorService(initialized_db_session, cache, engine)

    cache.set(quote("4.080"))
    first = monitor.evaluate_all(now=NOW)[0]
    assert first.state == RuntimeState.READY_TO_RETURN
    assert v.first_target_reached_at == NOW and v.last_target_reached_at == NOW

    cache.set(quote("4.082", NOW + timedelta(seconds=5)))
    second = monitor.evaluate_all(now=NOW + timedelta(seconds=5))[0]
    assert second.state == RuntimeState.READY_TO_RETURN
    assert v.last_target_reached_at == NOW

    cache.set(quote("4.100", NOW - timedelta(minutes=1)))
    stale = monitor.evaluate_all(now=NOW)[0]
    assert stale.state == RuntimeState.QUOTE_STALE
    assert initialized_db_session.get(MonitorState, v.id).runtime_state == RuntimeState.QUOTE_STALE.value

    cache.set(quote("4.100", NOW + timedelta(seconds=10)))
    recovered = monitor.evaluate_all(now=NOW + timedelta(seconds=10))[0]
    assert recovered.state == RuntimeState.READY_TO_RETURN
    assert v.last_target_reached_at == NOW + timedelta(seconds=10)

    cache.set(quote("4.010", NOW + timedelta(seconds=20)))
    fallen = monitor.evaluate_all(now=NOW + timedelta(seconds=20))[0]
    assert fallen.state == RuntimeState.IN_FLIGHT


def test_monitor_uses_last_close_while_market_is_closed(initialized_db_session):
    v = voyage(initialized_db_session)
    saturday = datetime(2026, 8, 29, 10, 0, tzinfo=TZ)
    friday_close = datetime(2026, 8, 28, 15, 0, tzinfo=TZ)
    cache = QuoteCache(30)
    cache.set(quote("4.100", friday_close))
    monitor = MonitorService(
        initialized_db_session,
        cache,
        ReturnEngine(FeeCalculator(FeeConfig()), near_return_buffer=Decimal("0.002")),
    )

    result = monitor.evaluate_all(now=saturday)[0]

    assert result.state == RuntimeState.TARGET_REACHED_NOT_SELLABLE
    assert result.runtime is not None
    assert result.runtime.monitor_price == Decimal("4.100")


class Recorder(Notifier):
    def __init__(self): self.events = []
    def send(self, event): self.events.append(event.event_type)


def test_alert_transitions_deduplicate_and_apply_cooldown(initialized_db_session):
    v = voyage(initialized_db_session)
    state = MonitorState(voyage_id=v.id, runtime_state=RuntimeState.IN_FLIGHT.value, updated_at=NOW)
    initialized_db_session.add(state); initialized_db_session.commit()
    recorder = Recorder(); service = AlertService(initialized_db_session, recorder, cooldown_minutes=30)

    near = MonitorEvaluation(v.id, RuntimeState.IN_FLIGHT, RuntimeState.NEAR_RETURN, None)
    assert [e.event_type for e in service.process(near, now=NOW)] == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert recorder.events == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert service.process(MonitorEvaluation(v.id, RuntimeState.NEAR_RETURN, RuntimeState.NEAR_RETURN, None), now=NOW + timedelta(minutes=1)) == []

    ready = service.process(MonitorEvaluation(v.id, RuntimeState.NEAR_RETURN, RuntimeState.READY_TO_RETURN, None), now=NOW + timedelta(minutes=2))
    assert ready[0].notified_at is None
    assert recorder.events == [AlertEventType.NEAR_RETURN_ENTERED.value]
    lost = service.process(MonitorEvaluation(v.id, RuntimeState.READY_TO_RETURN, RuntimeState.IN_FLIGHT, None), now=NOW + timedelta(minutes=31))
    assert lost[0].event_type == AlertEventType.TARGET_LOST.value
    assert recorder.events[-1] == AlertEventType.TARGET_LOST.value


def test_settings_resize_slots_and_update_fee_config(initialized_db_session):
    service = SettingsService(initialized_db_session)
    updated = service.update(SettingsUpdate(slot_count=12, default_slot_amount=Decimal("40000"), sell_commission_rate=Decimal("0.001"), return_price_mode="LAST"))
    assert updated.slot_count == 12
    assert len(CapitalService(initialized_db_session).list_slots()) == 12
    assert service.fee_config().sell_commission_rate == Decimal("0.001")
    assert updated.return_price_mode == "LAST"


def test_long_voyage_alert_is_emitted_once(initialized_db_session):
    v = voyage(initialized_db_session)
    recorder = Recorder(); service = AlertService(initialized_db_session, recorder, cooldown_minutes=0)
    first = service.process_long_voyage(v.id, 10, 10, now=NOW)
    second = service.process_long_voyage(v.id, 11, 10, now=NOW + timedelta(days=1))
    assert first is not None and first.event_type == AlertEventType.LONG_VOYAGE.value
    assert second is None
