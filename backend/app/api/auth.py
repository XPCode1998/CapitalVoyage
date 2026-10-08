from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.common import success
from app.auth.schemas import CredentialsUpdate, LoginInput
from app.auth.service import AuthService
from app.db.session import get_db


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/session")
def session_status(request: Request):
    return success({"authenticated": bool(request.session.get("authenticated")), "username": request.session.get("username")})


@router.post("/login")
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    account = AuthService(db).authenticate(payload.username, payload.password)
    request.session.clear()
    request.session.update({"authenticated": True, "username": account.username})
    return success({"username": account.username})


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return success({"ok": True})


@router.put("/credentials")
def update_credentials(payload: CredentialsUpdate, request: Request, db: Session = Depends(get_db)):
    account = AuthService(db).update_credentials(payload)
    request.session["username"] = account.username
    return success({"username": account.username})
