from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService, model_snapshot
from app.capital.models import CapitalSlot
from app.capital.service import CapitalService
from app.core.config import AppConfig, get_config
from app.core.enums import AuditAction, ReturnPriceMode, SlotStatus
from app.core.errors import DomainError
from app.core.time import now_shanghai
from app.return_engine.models import FeeConfig
from app.settings.models import AppSettings
from app.settings.schemas import SettingsUpdate


class SettingsService:
    SETTINGS_ID = 1

    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    def initialize(self, config: AppConfig | None = None, *, commit: bool = True) -> AppSettings:
        current = self.session.get(AppSettings, self.SETTINGS_ID)
        if current is not None:
            return current
        cfg = config or get_config()
        current = AppSettings(
            id=self.SETTINGS_ID,
            total_capital=Decimal(cfg.default_capital),
            slot_count=cfg.default_slot_count,
            default_slot_amount=Decimal(cfg.default_slot_amount),
            default_target_return=Decimal(cfg.default_target_return),
            near_return_buffer=Decimal(cfg.near_return_buffer),
            long_voyage_days=cfg.long_voyage_days,
            market_provider=cfg.market_provider,
            market_poll_interval_seconds=cfg.market_poll_interval_seconds,
            market_quote_stale_seconds=cfg.market_quote_stale_seconds,
            return_price_mode=cfg.return_price_mode,
            buy_commission_rate=Decimal(cfg.buy_commission_rate),
            sell_commission_rate=Decimal(cfg.sell_commission_rate),
            minimum_buy_commission=Decimal(cfg.minimum_buy_commission),
            minimum_sell_commission=Decimal(cfg.minimum_sell_commission),
            other_buy_fee_rate=Decimal(cfg.other_buy_fee_rate),
            other_sell_fee_rate=Decimal(cfg.other_sell_fee_rate),
            notification_provider=cfg.notification_provider,
            notification_webhook_url=cfg.notification_webhook_url,
            alert_cooldown_minutes=cfg.alert_cooldown_minutes,
        )
        self.session.add(current)
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(current)
        return current

    def get(self) -> AppSettings:
        return self.session.get(AppSettings, self.SETTINGS_ID) or self.initialize()

    def update(self, payload: SettingsUpdate) -> AppSettings:
        settings = self.get()
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if "return_price_mode" in changes:
            changes["return_price_mode"] = ReturnPriceMode(changes["return_price_mode"].upper()).value
        if "market_provider" in changes and changes["market_provider"].lower() != "akshare":
            raise DomainError("MARKET_UNAVAILABLE", "V1 仅支持 akshare 行情源", 400)
        if "notification_provider" in changes:
            value = changes["notification_provider"].lower()
            if value not in {"none", "console", "feishu", "ntfy"}:
                raise DomainError("INVALID_SETTINGS", "不支持的通知方式", 400)
            changes["notification_provider"] = value
        self._resize_slots(settings, changes)
        before = model_snapshot(settings)
        for field, value in changes.items():
            setattr(settings, field, value)
        settings.updated_at = now_shanghai()
        pool = CapitalService(self.session).get_pool()
        pool.total_capital = settings.total_capital
        pool.default_target_return = settings.default_target_return
        pool.updated_at = now_shanghai()
        self.session.flush()
        self.audit.record(AuditAction.UPDATE_SETTINGS, "AppSettings", settings.id, before=before, after=model_snapshot(settings))
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def _resize_slots(self, settings: AppSettings, changes: dict) -> None:
        new_count = int(changes.get("slot_count", settings.slot_count))
        new_amount = changes.get("default_slot_amount", settings.default_slot_amount)
        slots = list(self.session.scalars(select(CapitalSlot).order_by(CapitalSlot.slot_no)).all())
        if new_count < len(slots):
            removable = [slot for slot in slots if slot.slot_no > new_count]
            if any(slot.status == SlotStatus.OCCUPIED for slot in removable):
                raise DomainError("SLOT_OCCUPIED", "不能删除正在使用的舱位", 409)
            for slot in removable:
                self.session.delete(slot)
        elif new_count > len(slots):
            existing = {slot.slot_no for slot in slots}
            for no in range(1, new_count + 1):
                if no not in existing:
                    self.session.add(CapitalSlot(slot_no=no, budget_amount=new_amount, status=SlotStatus.AVAILABLE))
        if "default_slot_amount" in changes:
            for slot in slots:
                if slot.status == SlotStatus.AVAILABLE:
                    slot.budget_amount = new_amount

    def fee_config(self) -> FeeConfig:
        s = self.get()
        return FeeConfig(
            buy_commission_rate=s.buy_commission_rate,
            sell_commission_rate=s.sell_commission_rate,
            minimum_buy_commission=s.minimum_buy_commission,
            minimum_sell_commission=s.minimum_sell_commission,
            other_buy_fee_rate=s.other_buy_fee_rate,
            other_sell_fee_rate=s.other_sell_fee_rate,
        )
