from __future__ import annotations

from decimal import Decimal

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# Import every mapped model before create_all so SQLAlchemy can resolve string
# relationships and include all Phase 1 tables in the metadata.
from app.audit import models as audit_models  # noqa: F401
from app.alert import models as alert_models  # noqa: F401
from app.capital import models as capital_models  # noqa: F401
from app.capital.service import CapitalService
from app.core.config import AppConfig, get_config
from app.db.base import Base
from app.db.session import engine as default_engine
from app.exit import models as exit_models  # noqa: F401
from app.security import models as security_models  # noqa: F401
from app.return_engine import monitor as monitor_models  # noqa: F401
from app.settings import models as settings_models  # noqa: F401
from app.settings.service import SettingsService
from app.voyage import models as voyage_models  # noqa: F401
from app.voyage.repository import VoyageRepository


def init_db(engine: Engine = default_engine, config: AppConfig | None = None) -> None:
    """Create the schema and idempotently seed the V1 ledger defaults."""

    resolved_config = config or get_config()
    Base.metadata.create_all(engine)

    with Session(bind=engine, autoflush=False, expire_on_commit=False) as session:
        try:
            CapitalService(session).initialize_defaults(
                total_capital=Decimal(str(resolved_config.default_capital)),
                slot_count=resolved_config.default_slot_count,
                slot_amount=Decimal(str(resolved_config.default_slot_amount)),
                default_target_return=Decimal(
                    str(resolved_config.default_target_return)
                ),
                commit=False,
            )
            VoyageRepository(session).ensure_sequence()
            SettingsService(session).initialize(resolved_config, commit=False)
            session.commit()
        except Exception:
            session.rollback()
            raise
