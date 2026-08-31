from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.common import success
from app.db.session import get_db
from app.return_engine.center import ReturnCenterService
from app.return_engine.engine import ReturnEngine
from app.return_engine.fee import FeeCalculator
from app.settings.service import SettingsService


router = APIRouter(prefix="/api/returns", tags=["Return Center"])


@router.get("/ready")
def ready_returns(request: Request, db: Session = Depends(get_db)):
    settings = SettingsService(db)
    current = settings.get()
    engine = ReturnEngine(FeeCalculator(settings.fee_config()), near_return_buffer=current.near_return_buffer)
    groups = ReturnCenterService(db, request.app.state.runtime.quote_cache, return_engine=engine, price_mode=current.return_price_mode).get_ready()
    return success(groups)

