from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime, DecimalType

if TYPE_CHECKING:
    from app.voyage.models import Voyage


class ExitTransaction(Base):
    __tablename__ = "exit_transactions"
    __table_args__ = (
        CheckConstraint(
            "CAST(exit_price AS NUMERIC) > 0",
            name="ck_exit_price_positive",
        ),
        CheckConstraint("total_quantity > 0", name="ck_exit_quantity_positive"),
        CheckConstraint(
            "CAST(total_fee AS NUMERIC) >= 0",
            name="ck_exit_fee_nonnegative",
        ),
        Index("ix_exit_symbol_time", "symbol", "exit_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exit_time: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    total_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_fee: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(), default=now_shanghai, nullable=False
    )

    allocations: Mapped[list["ExitAllocation"]] = relationship(
        back_populates="exit_transaction",
        cascade="all, delete-orphan",
        order_by="ExitAllocation.id",
    )


class ExitAllocation(Base):
    __tablename__ = "exit_allocations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_allocation_quantity_positive"),
        CheckConstraint(
            "CAST(allocated_fee AS NUMERIC) >= 0",
            name="ck_allocation_fee_nonnegative",
        ),
        CheckConstraint(
            "CAST(realized_cost AS NUMERIC) > 0",
            name="ck_allocation_cost_positive",
        ),
        UniqueConstraint(
            "exit_transaction_id",
            "voyage_id",
            name="uq_exit_allocation_transaction_voyage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exit_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("exit_transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voyage_id: Mapped[int] = mapped_column(
        ForeignKey("voyages.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allocated_fee: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    realized_cost: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    realized_profit: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)
    realized_return: Mapped[Decimal] = mapped_column(DecimalType(), nullable=False)

    exit_transaction: Mapped[ExitTransaction] = relationship(back_populates="allocations")
    voyage: Mapped["Voyage"] = relationship(back_populates="exit_allocations")
