from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import now_shanghai
from app.db.base import Base
from app.db.types import AwareDateTime


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    voyage_id: Mapped[int] = mapped_column(ForeignKey("voyages.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(48))
    to_state: Mapped[str] = mapped_column(String(48), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), default=now_shanghai, nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(AwareDateTime())

