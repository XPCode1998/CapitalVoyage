from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SlotStatus
from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime, DecimalType

if TYPE_CHECKING:
    from app.voyage.models import Voyage


class CapitalPool(Base):
    __tablename__ = "capital_pools"
    __table_args__ = (
        CheckConstraint(
            "CAST(total_capital AS NUMERIC) > 0",
            name="ck_capital_pool_total_positive",
        ),
        CheckConstraint(
            "CAST(default_target_return AS NUMERIC) > 0",
            name="ck_capital_pool_target_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    total_capital: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    default_target_return: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False
    )


class CapitalSlot(Base):
    __tablename__ = "capital_slots"
    __table_args__ = (
        CheckConstraint("slot_no > 0", name="ck_capital_slot_no_positive"),
        CheckConstraint(
            "CAST(budget_amount AS NUMERIC) > 0",
            name="ck_capital_slot_budget_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_no: Mapped[int] = mapped_column(unique=True, nullable=False, index=True)
    budget_amount: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    status: Mapped[SlotStatus] = mapped_column(
        SAEnum(
            SlotStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="slot_status",
        ),
        default=SlotStatus.AVAILABLE,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False
    )

    voyages: Mapped[list["Voyage"]] = relationship(back_populates="slot")
