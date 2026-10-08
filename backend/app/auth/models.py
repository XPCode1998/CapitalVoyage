from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime


class LocalAccount(Base):
    __tablename__ = "local_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=now_shanghai, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False)
