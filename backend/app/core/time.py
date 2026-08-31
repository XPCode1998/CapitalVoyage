from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_config


def app_timezone() -> ZoneInfo:
    return ZoneInfo(get_config().timezone)


def now_shanghai() -> datetime:
    return datetime.now(app_timezone())


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=app_timezone())
    return value.astimezone(app_timezone())

