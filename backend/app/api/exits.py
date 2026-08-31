from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common import success
from app.db.session import get_db
from app.exit.schemas import ExitCreate
from app.exit.service import ExitService


router = APIRouter(prefix="/api/exits", tags=["Exits"])


@router.post("", status_code=201)
def create_exit(payload: ExitCreate, db: Session = Depends(get_db)):
    transaction = ExitService(db).create(payload)
    return success(transaction, 201)

