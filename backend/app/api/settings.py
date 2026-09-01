from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.common import success
from app.core.errors import DomainError
from app.db.session import get_db
from app.notification.feishu import FeishuNotifier
from app.settings.schemas import SettingsUpdate
from app.settings.service import SettingsService


router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return success(SettingsService(db).get())


@router.put("")
def update_settings(payload: SettingsUpdate, request: Request, db: Session = Depends(get_db)):
    updated = SettingsService(db).update(payload)
    request.app.state.runtime.quote_cache.stale_after_seconds = updated.market_quote_stale_seconds
    request.app.state.runtime.poller.normal_interval_seconds = updated.market_poll_interval_seconds
    return success(updated)


@router.post("/notification/test")
def test_feishu_notification(db: Session = Depends(get_db)):
    settings = SettingsService(db).get()
    if settings.notification_provider != "feishu" or not settings.notification_webhook_url:
        raise DomainError("NOTIFICATION_NOT_CONFIGURED", "请先保存飞书 Webhook 配置", 400)
    try:
        FeishuNotifier(settings.notification_webhook_url).send_text(
            "飞书通知测试成功。交易时段内，接近返航将每 5 分钟更新；可返航将每 1 分钟更新。"
        )
    except Exception as exc:
        raise DomainError("NOTIFICATION_DELIVERY_FAILED", f"飞书测试消息发送失败：{exc}", 502) from exc
    return success({"message": "测试消息已发送至飞书"})
