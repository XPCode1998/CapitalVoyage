from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select

from app.core.config import AppConfig, PROJECT_ROOT
from app.db.session import make_engine
from app.db.types import AwareDateTime, DecimalType


def _typed_values_table() -> Table:
    metadata = MetaData()
    return Table(
        "typed_values",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", DecimalType(), nullable=False),
        Column("observed_at", AwareDateTime(), nullable=False),
    )


def test_decimal_and_aware_datetime_round_trip_losslessly() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = _typed_values_table()
    table.metadata.create_all(engine)
    amount = Decimal("12345678901234567890.0012300")
    observed_at = datetime(
        2026,
        8,
        29,
        14,
        3,
        2,
        987654,
        tzinfo=timezone(timedelta(hours=8)),
    )

    with engine.begin() as connection:
        connection.execute(
            insert(table).values(amount=amount, observed_at=observed_at)
        )
        raw_amount = connection.exec_driver_sql(
            "SELECT amount FROM typed_values"
        ).scalar_one()
        stored_amount, stored_time = connection.execute(
            select(table.c.amount, table.c.observed_at)
        ).one()

    assert raw_amount == "12345678901234567890.0012300"
    assert stored_amount.as_tuple() == amount.as_tuple()
    assert stored_time == observed_at
    assert stored_time.utcoffset() == timedelta(hours=8)
    engine.dispose()


@pytest.mark.parametrize("value", [1.25, True, Decimal("NaN"), Decimal("Infinity")])
def test_decimal_type_rejects_unsafe_values(value: object) -> None:
    decimal_type = DecimalType()

    with pytest.raises((TypeError, ValueError)):
        decimal_type.process_bind_param(value, dialect=None)  # type: ignore[arg-type]


def test_aware_datetime_rejects_naive_values() -> None:
    aware_type = AwareDateTime()

    with pytest.raises(ValueError, match="timezone-aware"):
        aware_type.process_bind_param(datetime(2026, 8, 29, 12, 0), dialect=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        aware_type.process_result_value("2026-08-29T12:00:00", dialect=None)


def test_file_sqlite_engine_enables_required_pragmas(tmp_path) -> None:
    database_path = tmp_path / "nested" / "capital_voyage.db"
    engine = make_engine(f"sqlite:///{database_path}")

    with engine.connect() as connection:
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()

    assert database_path.exists()
    assert foreign_keys == 1
    assert busy_timeout == 5000
    assert journal_mode.lower() == "wal"
    engine.dispose()


def test_relative_sqlite_url_is_resolved_from_backend_directory() -> None:
    config = AppConfig(
        database_url="sqlite:///../data/test.db",
        _env_file=None,
    )

    assert config.resolved_database_url == f"sqlite:///{PROJECT_ROOT / 'data' / 'test.db'}"


def test_in_memory_sqlite_url_is_not_resolved_as_a_file() -> None:
    config = AppConfig(database_url="sqlite:///:memory:", _env_file=None)

    assert config.resolved_database_url == "sqlite:///:memory:"
