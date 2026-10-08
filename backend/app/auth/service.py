from __future__ import annotations

import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session

from app.auth.models import LocalAccount
from app.auth.schemas import CredentialsUpdate
from app.core.errors import DomainError
from app.core.time import now_shanghai


DEFAULT_USERNAME = "xp"
DEFAULT_PASSWORD = "980127"
HASH_NAME = "sha256"
HASH_ITERATIONS = 600_000


def _password_hash(password: str, *, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt.encode("ascii"), HASH_ITERATIONS)
    return f"pbkdf2_{HASH_NAME}${HASH_ITERATIONS}${salt}${digest.hex()}"


def _matches(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$", 3)
        if algorithm != f"pbkdf2_{HASH_NAME}":
            return False
        candidate = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt.encode("ascii"), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest)
    except (TypeError, ValueError):
        return False


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def initialize(self, *, commit: bool = True) -> LocalAccount:
        account = self.session.get(LocalAccount, 1)
        if account is None:
            account = LocalAccount(id=1, username=DEFAULT_USERNAME, password_hash=_password_hash(DEFAULT_PASSWORD))
            self.session.add(account)
            self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(account)
        return account

    def account(self) -> LocalAccount:
        return self.session.get(LocalAccount, 1) or self.initialize()

    def authenticate(self, username: str, password: str) -> LocalAccount:
        account = self.account()
        if not hmac.compare_digest(account.username, username.strip()) or not _matches(password, account.password_hash):
            raise DomainError("INVALID_CREDENTIALS", "账号或密码错误", 401)
        return account

    def update_credentials(self, payload: CredentialsUpdate) -> LocalAccount:
        account = self.account()
        if not _matches(payload.current_password, account.password_hash):
            raise DomainError("INVALID_CREDENTIALS", "当前密码错误", 401)
        username = payload.username.strip() if payload.username else account.username
        if not username:
            raise DomainError("INVALID_CREDENTIALS", "账号不能为空", 400)
        account.username = username
        if payload.new_password:
            account.password_hash = _password_hash(payload.new_password)
        account.updated_at = now_shanghai()
        self.session.commit()
        self.session.refresh(account)
        return account
