from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common import success
from app.api.helpers import voyage_dict
from app.capital.service import CapitalService
from app.core.enums import VoyageStatus
from app.db.session import get_db
from app.return_engine.monitor import MonitorState
from app.voyage.repository import VoyageRepository


router = APIRouter(prefix="/api/slots", tags=["Slots"])


@router.get("")
def list_slots(db: Session = Depends(get_db)):
    voyages = VoyageRepository(db).list(status=VoyageStatus.OPEN)
    by_slot = {v.slot_id: v for v in voyages}
    result = []
    for slot in CapitalService(db).list_slots():
        voyage = by_slot.get(slot.id)
        result.append({
            "id": slot.id, "slot_no": slot.slot_no, "budget_amount": slot.budget_amount,
            "status": slot.status, "voyage": voyage_dict(voyage, db.get(MonitorState, voyage.id)) if voyage else None,
        })
    return success(result)

