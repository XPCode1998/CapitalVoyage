from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.common import success
from app.api.helpers import voyage_dict
from app.db.session import get_db
from app.return_engine.fee import FeeCalculator
from app.return_engine.monitor import MonitorState
from app.return_engine.target import TargetPriceCalculator
from app.security.models import Security
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.settings.service import SettingsService
from app.voyage.schemas import VoyageCreate, VoyageUpdate
from app.voyage.service import VoyageService


router = APIRouter(prefix="/api/voyages", tags=["Voyages"])


class VoyagePreview(BaseModel):
    entry_price: Decimal = Field(gt=0)
    entry_quantity: int = Field(gt=0)
    entry_fee: Decimal = Field(default=Decimal("0"), ge=0)
    target_return: Decimal = Field(default=Decimal("0.02"), gt=0)


@router.get("")
def list_voyages(db: Session = Depends(get_db)):
    items = VoyageService(db).list()
    return success([voyage_dict(v, db.get(MonitorState, v.id)) for v in items])


@router.get("/{voyage_id}")
def get_voyage(voyage_id: int, db: Session = Depends(get_db)):
    voyage = VoyageService(db).get(voyage_id)
    return success(voyage_dict(voyage, db.get(MonitorState, voyage.id)))


@router.post("", status_code=201)
def create_voyage(payload: VoyageCreate, request: Request, db: Session = Depends(get_db)):
    if db.get(Security, payload.symbol) is None:
        quote = request.app.state.runtime.quote_cache.get(payload.symbol)
        SecurityService(db).create(SecurityCreate(symbol=payload.symbol, name=quote.name if quote else payload.symbol))
    voyage = VoyageService(db).create(payload)
    return success(voyage_dict(voyage), 201)


@router.post("/preview")
def preview_voyage(payload: VoyagePreview, db: Session = Depends(get_db)):
    settings = SettingsService(db)
    calculator = FeeCalculator(settings.fee_config())
    entry_cost = payload.entry_price * payload.entry_quantity + payload.entry_fee
    target = TargetPriceCalculator(calculator).calculate(
        remaining_cost=entry_cost,
        remaining_quantity=payload.entry_quantity,
        target_return=payload.target_return,
    )
    return success({"actual_investment": entry_cost, "target_price": target})


@router.patch("/{voyage_id}")
def update_voyage(voyage_id: int, payload: VoyageUpdate, db: Session = Depends(get_db)):
    voyage = VoyageService(db).update(voyage_id, payload)
    return success(voyage_dict(voyage, db.get(MonitorState, voyage.id)))


@router.post("/{voyage_id}/cancel")
def cancel_voyage(voyage_id: int, db: Session = Depends(get_db)):
    voyage = VoyageService(db).cancel(voyage_id)
    return success(voyage_dict(voyage, db.get(MonitorState, voyage.id)))

