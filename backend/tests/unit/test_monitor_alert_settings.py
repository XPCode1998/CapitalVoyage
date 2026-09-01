from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
import httpx
import pytest

from app.alert.models import AlertEvent
from app.alert.service import AlertService
from app.capital.service import CapitalService
from app.core.enums import AlertEventType, RuntimeState, SettlementMode, SlotStatus
from app.core.errors import DomainError
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.notification.base import Notifier
from app.notification.feishu import FeishuNotifier
from app.notification.payload import AlertNotification
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


def test_alert_only_notifies_near_and_ready_on_their_own_intervals(initialized_db_session):
    v = voyage(initialized_db_session)
    state = MonitorState(voyage_id=v.id, runtime_state=RuntimeState.IN_FLIGHT.value, updated_at=NOW)
    initialized_db_session.add(state); initialized_db_session.commit()
    recorder = Recorder(); service = AlertService(initialized_db_session, recorder)

    near = MonitorEvaluation(v.id, RuntimeState.IN_FLIGHT, RuntimeState.NEAR_RETURN, None)
    assert [e.event_type for e in service.process(near, now=NOW)] == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert recorder.events == [AlertEventType.NEAR_RETURN_ENTERED.value]
    unchanged_near = MonitorEvaluation(v.id, RuntimeState.NEAR_RETURN, RuntimeState.NEAR_RETURN, None)
    assert service.process(unchanged_near, now=NOW + timedelta(minutes=4)) == []
    assert [e.event_type for e in service.process(unchanged_near, now=NOW + timedelta(minutes=5))] == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert recorder.events == [AlertEventType.NEAR_RETURN_ENTERED.value, AlertEventType.NEAR_RETURN_ENTERED.value]

    ready = service.process(MonitorEvaluation(v.id, RuntimeState.NEAR_RETURN, RuntimeState.READY_TO_RETURN, None), now=NOW + timedelta(minutes=6))
    assert [event.event_type for event in ready] == [AlertEventType.READY_TO_RETURN.value]
    assert recorder.events[-1] == AlertEventType.READY_TO_RETURN.value
    unchanged_ready = MonitorEvaluation(v.id, RuntimeState.READY_TO_RETURN, RuntimeState.READY_TO_RETURN, None)
    assert service.process(unchanged_ready, now=NOW + timedelta(minutes=6, seconds=30)) == []
    assert [e.event_type for e in service.process(unchanged_ready, now=NOW + timedelta(minutes=7))] == [AlertEventType.READY_TO_RETURN.value]
    assert recorder.events.count(AlertEventType.READY_TO_RETURN.value) == 2

    sent_before_loss = list(recorder.events)
    lost = service.process(MonitorEvaluation(v.id, RuntimeState.READY_TO_RETURN, RuntimeState.IN_FLIGHT, None), now=NOW + timedelta(minutes=8))
    assert lost[0].event_type == AlertEventType.TARGET_LOST.value
    assert lost[0].notified_at is None
    assert recorder.events == sent_before_loss


def test_alert_notifications_are_suppressed_until_market_reopens(initialized_db_session):
    v = voyage(initialized_db_session)
    state = MonitorState(voyage_id=v.id, runtime_state=RuntimeState.IN_FLIGHT.value, updated_at=NOW)
    initialized_db_session.add(state); initialized_db_session.commit()
    recorder = Recorder(); service = AlertService(initialized_db_session, recorder)

    # The lunchtime break is not a trading session: retain the state transition
    # for audit, but do not create a periodic notification or call the notifier.
    lunch = datetime(2026, 8, 31, 12, 0, tzinfo=TZ)
    entered = service.process(
        MonitorEvaluation(v.id, RuntimeState.IN_FLIGHT, RuntimeState.NEAR_RETURN, None),
        now=lunch,
    )
    assert [event.event_type for event in entered] == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert entered[0].notified_at is None
    assert recorder.events == []

    # The same state is sent once the afternoon session has reopened.
    afternoon = datetime(2026, 8, 31, 13, 1, tzinfo=TZ)
    resumed = service.process(
        MonitorEvaluation(v.id, RuntimeState.NEAR_RETURN, RuntimeState.NEAR_RETURN, None),
        now=afternoon,
    )
    assert [event.event_type for event in resumed] == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert recorder.events == [AlertEventType.NEAR_RETURN_ENTERED.value]
    assert resumed[0].notified_at == afternoon


def test_settings_resize_slots_and_update_fee_config(initialized_db_session):
    service = SettingsService(initialized_db_session)
    updated = service.update(SettingsUpdate(slot_count=12, default_slot_amount=Decimal("40000"), sell_commission_rate=Decimal("0.001"), return_price_mode="LAST"))
    assert updated.slot_count == 12
    assert len(CapitalService(initialized_db_session).list_slots()) == 12
    assert service.fee_config().sell_commission_rate == Decimal("0.001")
    assert updated.return_price_mode == "LAST"


def test_long_voyage_alert_is_emitted_once(initialized_db_session):
    v = voyage(initialized_db_session)
    recorder = Recorder(); service = AlertService(initialized_db_session, recorder)
    first = service.process_long_voyage(v.id, 10, 10, now=NOW)
    second = service.process_long_voyage(v.id, 11, 10, now=NOW + timedelta(days=1))
    assert first is not None and first.event_type == AlertEventType.LONG_VOYAGE.value
    assert second is None
    assert recorder.events == []


def test_feishu_notifier_rejects_business_error_in_success_response(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return httpx.Response(
            200,
            json={"code": 19024, "msg": "Key Words Not Found"},
            request=httpx.Request("POST", "https://open.feishu.cn/open-apis/bot/v2/hook/example"),
        )

    monkeypatch.setattr("app.notification.feishu.httpx.post", fake_post)

    with pytest.raises(RuntimeError, match="19024"):
        FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/example").send_text("测试")


def test_feishu_notifier_sends_a_ready_to_return_card(monkeypatch):
    captured = {}

    def fake_post(*_args, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(
            200,
            json={"code": 0},
            request=httpx.Request("POST", "https://open.feishu.cn/open-apis/bot/v2/hook/example"),
        )

    monkeypatch.setattr("app.notification.feishu.httpx.post", fake_post)
    FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/example").send(
        AlertNotification(
            event_type=AlertEventType.READY_TO_RETURN.value,
            message="unused by Feishu cards",
            voyage_no="QC-0001",
            symbol="510300",
            security_name="沪深300ETF",
            slot_no=3,
            net_return=Decimal("0.0214"),
            target_return=Decimal("0.0200"),
            distance_to_target=Decimal("0"),
            monitor_price=Decimal("4.092"),
            target_price=Decimal("4.080"),
            remaining_quantity=12500,
            quote_time=NOW,
            interval_minutes=1,
        )
    )

    assert captured["msg_type"] == "interactive"
    assert captured["card"]["header"]["template"] == "green"
    assert captured["card"]["header"]["title"]["content"] == "可返航 · READY TO RETURN"
    fields = captured["card"]["elements"][2]["fields"]
    assert "+2.14%" in fields[0]["text"]["content"]
    assert "+0.14pp" in fields[2]["text"]["content"]
    assert "12,500 份" in fields[3]["text"]["content"]


def test_feishu_settings_requires_https_webhook(initialized_db_session):
    with pytest.raises(DomainError, match="HTTPS"):
        SettingsService(initialized_db_session).update(
            SettingsUpdate(notification_provider="feishu", notification_webhook_url="http://example.com/hook")
        )
