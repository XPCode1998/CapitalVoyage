from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.common import success
from app.db.session import get_db
from app.reconcile.service import ReconcileService


router = APIRouter(prefix="/api/reconcile", tags=["Reconcile"])


class ReconcileInput(BaseModel):
    symbol: str
    broker_quantity: int = Field(ge=0)


@router.post("")
def reconcile(payload: ReconcileInput, db: Session = Depends(get_db)):
    return success(ReconcileService(db).reconcile(payload.symbol.strip().upper(), payload.broker_quantity))

