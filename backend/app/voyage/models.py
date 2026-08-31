from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import VoyageStatus
from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime, DecimalType

if TYPE_CHECKING:
    from app.capital.models import CapitalSlot
    from app.exit.models import ExitAllocation
    from app.security.models import Security


class VoyageSequence(Base):
    """Persistent sequence independent from Voyage rows.

    Keeping the counter in its own table ensures a deleted Voyage number is never
    reused. The repository increments it atomically before formatting the number.
    """

    __tablename__ = "voyage_sequences"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    next_value: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


class Voyage(Base):
    __tablename__ = "voyages"
    __table_args__ = (
        CheckConstraint(
            "CAST(entry_price AS NUMERIC) > 0",
            name="ck_voyage_entry_price_positive",
        ),
        CheckConstraint("entry_quantity > 0", name="ck_voyage_entry_quantity_positive"),
        CheckConstraint(
            "CAST(entry_fee AS NUMERIC) >= 0",
            name="ck_voyage_entry_fee_nonnegative",
        ),
        CheckConstraint(
            "CAST(target_return AS NUMERIC) > 0",
            name="ck_voyage_target_positive",
        ),
        # SQLite partial unique index is the final guard against two concurrent
        # requests occupying the same Slot. Service code also performs a friendly
        # transactional check before inserting.
        Index(
            "uq_voyages_one_open_per_slot",
            "slot_id",
            unique=True,
            sqlite_where=text("status = 'OPEN'"),
        ),
        Index("ix_voyages_symbol_status", "symbol", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    voyage_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("capital_slots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("securities.symbol", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entry_time: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    entry_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entry_fee: Mapped[Decimal] = mapped_column(DecimalType(), default=Decimal("0"), nullable=False)
    target_return: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    sellable_at: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    status: Mapped[VoyageStatus] = mapped_column(
        SAEnum(
            VoyageStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="voyage_status",
        ),
        default=VoyageStatus.OPEN,
        nullable=False,
        index=True,
    )
    first_target_reached_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    last_target_reached_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, onupdate=now_shanghai, nullable=False
    )

    slot: Mapped["CapitalSlot"] = relationship(back_populates="voyages")
    security: Mapped["Security"] = relationship(back_populates="voyages")
    exit_allocations: Mapped[list["ExitAllocation"]] = relationship(
        back_populates="voyage"
    )

    @hybrid_property
    def remaining_quantity(self) -> int:
        """Derive the open quantity; this value is intentionally never persisted."""

        return self.entry_quantity - sum(
            allocation.quantity for allocation in self.exit_allocations
        )

    @property
    def entry_cost(self) -> Decimal:
        return self.entry_price * self.entry_quantity + self.entry_fee

    @property
    def unit_cost(self) -> Decimal:
        return self.entry_cost / self.entry_quantity
