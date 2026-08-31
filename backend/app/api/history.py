from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common import success
from app.db.session import get_db
from app.history.service import HistoryService


router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("")
def history(db: Session = Depends(get_db)):
    return success(HistoryService(db).get())

