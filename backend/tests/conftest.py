from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.db.base import Base
from app.db.init import init_db
from app.db.session import make_engine

# Importing all model modules registers their tables on the shared metadata.
from app.audit import models as audit_models  # noqa: F401, E402
from app.capital import models as capital_models  # noqa: F401, E402
from app.exit import models as exit_models  # noqa: F401, E402
from app.security import models as security_models  # noqa: F401, E402
from app.voyage import models as voyage_models  # noqa: F401, E402


@pytest.fixture
def database_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'capital_voyage_test.db'}"


@pytest.fixture
def app_config(database_url: str) -> AppConfig:
    return AppConfig(
        database_url=database_url,
        default_capital="500000",
        default_slot_count=10,
        default_slot_amount="50000",
        default_target_return="0.02",
        scheduler_enabled=False,
    )


@pytest.fixture
def db_engine(database_url: str) -> Iterator[Engine]:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(
        bind=db_engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    with factory() as session:
        yield session


@pytest.fixture
def initialized_db_session(
    db_engine: Engine,
    app_config: AppConfig,
) -> Iterator[Session]:
    init_db(engine=db_engine, config=app_config)
    factory = sessionmaker(
        bind=db_engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    with factory() as session:
        yield session
