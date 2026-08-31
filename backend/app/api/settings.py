from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.common import success
from app.db.session import get_db
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
