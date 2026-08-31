from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SettlementMode
from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime

if TYPE_CHECKING:
    from app.voyage.models import Voyage


class Security(Base):
    __tablename__ = "securities"
    __table_args__ = (
        CheckConstraint("trade_unit > 0", name="ck_security_trade_unit_positive"),
    )

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, default="CN")
    settlement_mode: Mapped[SettlementMode] = mapped_column(
        SAEnum(
            SettlementMode,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="settlement_mode",
        ),
        default=SettlementMode.T1,
        nullable=False,
    )
    trade_unit: Mapped[int] = mapped_column(default=100, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False
    )

    voyages: Mapped[list["Voyage"]] = relationship(back_populates="security")

