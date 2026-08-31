from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.capital.models import CapitalPool, CapitalSlot
from app.capital.service import CapitalService
from app.core.config import AppConfig
from app.core.enums import SettlementMode, SlotStatus, VoyageStatus
from app.core.errors import DomainError
from app.db.init import init_db
from app.db.types import DecimalType
from app.exit.models import ExitAllocation, ExitTransaction
from app.exit.schemas import ExitAllocationInput, ExitCreate
from app.exit.service import ExitService
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.voyage.schemas import VoyageCreate, VoyageUpdate
from app.voyage.repository import VoyageRepository
from app.voyage.service import VoyageService


SHANGHAI = ZoneInfo("Asia/Shanghai")
ENTRY_TIME = datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)
SELLABLE_AT = datetime(2026, 8, 31, 9, 30, tzinfo=SHANGHAI)
EXIT_TIME = datetime(2026, 8, 31, 10, 30, tzinfo=SHANGHAI)


def _create_security(
    session: Session,
    symbol: str = "510300",
    name: str = "沪深300ETF",
) -> None:
    SecurityService(session).create(
        SecurityCreate(
            symbol=symbol,
            name=name,
            market="CN",
            settlement_mode=SettlementMode.T1,
            trade_unit=100,
            enabled=True,
        )
    )


def _create_voyage(
    session: Session,
    slot_id: int,
    *,
    symbol: str = "510300",
    entry_price: str = "4.000",
    entry_quantity: int = 12_500,
    entry_fee: str = "0",
):
    return VoyageService(session).create(
        VoyageCreate(
            slot_id=slot_id,
            symbol=symbol,
            entry_time=ENTRY_TIME,
            entry_price=Decimal(entry_price),
            entry_quantity=entry_quantity,
            entry_fee=Decimal(entry_fee),
            target_return=Decimal("0.02"),
            sellable_at=SELLABLE_AT,
        )
    )


def _slots(session: Session) -> list[CapitalSlot]:
    return CapitalService(session).list_slots()


def test_decimal_type_round_trips_without_precision_loss(db_engine: Engine) -> None:
    metadata = MetaData()
    probe = Table(
        "decimal_precision_probe",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", DecimalType(), nullable=False),
    )
    metadata.create_all(db_engine)
    expected = Decimal("12345678901234567890.12345678901234567890")

    with db_engine.begin() as connection:
        connection.execute(insert(probe).values(id=1, amount=expected))
        restored = connection.execute(select(probe.c.amount)).scalar_one()
        raw = connection.exec_driver_sql(
            "SELECT amount FROM decimal_precision_probe WHERE id = 1"
        ).scalar_one()

    assert restored == expected
    assert isinstance(restored, Decimal)
    assert raw == "12345678901234567890.12345678901234567890"


def test_decimal_string_checks_reject_noncanonical_zero(db_engine: Engine) -> None:
    # DecimalType intentionally stores text. A lexical CHECK such as value > '0'
    # incorrectly accepts '0.0'; the schema must cast only for sign validation.
    with Session(db_engine) as session:
        session.add(
            CapitalPool(
                name="invalid",
                total_capital=Decimal("0.0"),
                default_target_return=Decimal("0.00"),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_init_db_seeds_default_pool_and_ten_slots_idempotently(
    initialized_db_session: Session,
    db_engine: Engine,
    app_config: AppConfig,
) -> None:
    init_db(engine=db_engine, config=app_config)

    pools = initialized_db_session.scalars(select(CapitalPool)).all()
    slots = _slots(initialized_db_session)

    assert len(pools) == 1
    assert pools[0].name == "CapitalVoyage"
    assert pools[0].total_capital == Decimal("500000")
    assert pools[0].default_target_return == Decimal("0.02")
    assert len(slots) == 10
    assert [slot.slot_no for slot in slots] == list(range(1, 11))
    assert all(slot.budget_amount == Decimal("50000") for slot in slots)
    assert all(slot.status == SlotStatus.AVAILABLE for slot in slots)


def test_create_voyage_occupies_slot_and_rejects_duplicate_open_voyage(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    service = VoyageService(initialized_db_session)

    voyage = _create_voyage(initialized_db_session, slot.id)

    assert voyage.voyage_no == "QC-0001"
    assert voyage.status == VoyageStatus.OPEN
    assert initialized_db_session.get(CapitalSlot, slot.id).status == SlotStatus.OCCUPIED

    with pytest.raises(DomainError) as raised:
        service.create(
            VoyageCreate(
                slot_id=slot.id,
                symbol="510300",
                entry_time=ENTRY_TIME,
                entry_price=Decimal("3.900"),
                entry_quantity=12_800,
                entry_fee=Decimal("0"),
                target_return=Decimal("0.02"),
                sellable_at=SELLABLE_AT,
            )
        )

    assert raised.value.code == "SLOT_OCCUPIED"
    assert service.get(voyage.id).status == VoyageStatus.OPEN


def test_cancel_voyage_releases_its_slot(initialized_db_session: Session) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    service = VoyageService(initialized_db_session)
    voyage = _create_voyage(initialized_db_session, slot.id)

    cancelled = service.cancel(voyage.id)

    assert cancelled.status == VoyageStatus.CANCELLED
    assert initialized_db_session.get(CapitalSlot, slot.id).status == SlotStatus.AVAILABLE


def test_reschedule_recalculates_t1_sellable_time(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    service = VoyageService(initialized_db_session)
    voyage = _create_voyage(initialized_db_session, slot.id)
    new_entry = datetime(2026, 8, 31, 10, 0, tzinfo=SHANGHAI)

    updated = service.update(
        voyage.id,
        VoyageUpdate(entry_time=new_entry, entry_price=Decimal("4.100")),
    )

    assert updated.entry_time == new_entry
    assert updated.entry_price == Decimal("4.100")
    assert updated.sellable_at == datetime(2026, 9, 1, 9, 30, tzinfo=SHANGHAI)


def test_single_voyage_exit_closes_voyage_and_releases_slot(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    voyage = _create_voyage(
        initialized_db_session,
        slot.id,
        entry_price="10",
        entry_quantity=100,
        entry_fee="5",
    )
    # Preload the relationship-backed dynamic property. It must not remain
    # cached after ExitAllocation rows are written through their foreign keys.
    assert voyage.remaining_quantity == 100

    transaction = ExitService(initialized_db_session).create(
        ExitCreate(
            symbol="510300",
            exit_time=EXIT_TIME,
            exit_price=Decimal("12"),
            total_quantity=100,
            total_fee=Decimal("2"),
            allocations=[ExitAllocationInput(voyage_id=voyage.id, quantity=100)],
        )
    )
    allocation = initialized_db_session.scalar(
        select(ExitAllocation).where(
            ExitAllocation.exit_transaction_id == transaction.id
        )
    )

    assert allocation is not None
    assert allocation.allocated_fee == Decimal("2")
    assert allocation.realized_cost == Decimal("1005")
    assert allocation.realized_profit == Decimal("193")
    assert allocation.realized_return == Decimal("193") / Decimal("1005")
    assert voyage.remaining_quantity == 0
    assert VoyageService(initialized_db_session).remaining_quantity(voyage.id) == 0
    assert VoyageService(initialized_db_session).get(voyage.id).status == VoyageStatus.CLOSED
    assert initialized_db_session.get(CapitalSlot, slot.id).status == SlotStatus.AVAILABLE


def test_one_exit_can_allocate_across_multiple_voyages(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    first_slot, second_slot = _slots(initialized_db_session)[:2]
    first = _create_voyage(
        initialized_db_session,
        first_slot.id,
        entry_price="10",
        entry_quantity=100,
    )
    second = _create_voyage(
        initialized_db_session,
        second_slot.id,
        entry_price="8",
        entry_quantity=50,
    )

    transaction = ExitService(initialized_db_session).create(
        ExitCreate(
            symbol="510300",
            exit_time=EXIT_TIME,
            exit_price=Decimal("11"),
            total_quantity=150,
            total_fee=Decimal("3"),
            allocations=[
                ExitAllocationInput(voyage_id=first.id, quantity=100),
                ExitAllocationInput(voyage_id=second.id, quantity=50),
            ],
        )
    )
    allocations = initialized_db_session.scalars(
        select(ExitAllocation)
        .where(ExitAllocation.exit_transaction_id == transaction.id)
        .order_by(ExitAllocation.id)
    ).all()

    assert [allocation.quantity for allocation in allocations] == [100, 50]
    assert [allocation.allocated_fee for allocation in allocations] == [
        Decimal("2"),
        Decimal("1"),
    ]
    assert sum((row.allocated_fee for row in allocations), Decimal("0")) == Decimal("3")
    assert VoyageService(initialized_db_session).get(first.id).status == VoyageStatus.CLOSED
    assert VoyageService(initialized_db_session).get(second.id).status == VoyageStatus.CLOSED
    assert initialized_db_session.get(CapitalSlot, first_slot.id).status == SlotStatus.AVAILABLE
    assert initialized_db_session.get(CapitalSlot, second_slot.id).status == SlotStatus.AVAILABLE


def test_partial_exit_keeps_voyage_open_until_final_quantity_is_sold(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    voyage = _create_voyage(
        initialized_db_session,
        slot.id,
        entry_quantity=125,
    )
    exit_service = ExitService(initialized_db_session)
    voyage_service = VoyageService(initialized_db_session)

    exit_service.create(
        ExitCreate(
            symbol="510300",
            exit_time=EXIT_TIME,
            exit_price=Decimal("4.100"),
            total_quantity=70,
            total_fee=Decimal("1.40"),
            allocations=[ExitAllocationInput(voyage_id=voyage.id, quantity=70)],
        )
    )

    assert voyage_service.remaining_quantity(voyage.id) == 55
    assert voyage_service.get(voyage.id).status == VoyageStatus.OPEN
    assert initialized_db_session.get(CapitalSlot, slot.id).status == SlotStatus.OCCUPIED

    exit_service.create(
        ExitCreate(
            symbol="510300",
            exit_time=EXIT_TIME,
            exit_price=Decimal("4.200"),
            total_quantity=55,
            total_fee=Decimal("1.10"),
            allocations=[ExitAllocationInput(voyage_id=voyage.id, quantity=55)],
        )
    )

    assert voyage_service.remaining_quantity(voyage.id) == 0
    assert voyage_service.get(voyage.id).status == VoyageStatus.CLOSED
    assert initialized_db_session.get(CapitalSlot, slot.id).status == SlotStatus.AVAILABLE


def test_concurrent_exits_cannot_over_allocate_same_voyage(
    initialized_db_session: Session,
    db_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    voyage = _create_voyage(
        initialized_db_session,
        slot.id,
        entry_quantity=100,
    )

    # Put both workers immediately in front of the no-op UPDATE. One obtains
    # SQLite's writer lock; the other must wait and then observe remaining=40.
    barrier = Barrier(2)
    original_lock = VoyageRepository.acquire_ledger_write_lock

    def synchronized_lock(repository: VoyageRepository) -> None:
        barrier.wait(timeout=5)
        original_lock(repository)

    monkeypatch.setattr(
        VoyageRepository,
        "acquire_ledger_write_lock",
        synchronized_lock,
    )
    factory = sessionmaker(
        bind=db_engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )

    def record_exit(minute: int) -> str:
        with factory() as session:
            try:
                ExitService(session).create(
                    ExitCreate(
                        symbol="510300",
                        exit_time=EXIT_TIME.replace(minute=minute),
                        exit_price=Decimal("4.100"),
                        total_quantity=60,
                        total_fee=Decimal("1.20"),
                        allocations=[
                            ExitAllocationInput(voyage_id=voyage.id, quantity=60)
                        ],
                    )
                )
            except DomainError as exc:
                return exc.code
            return "OK"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(record_exit, (31, 32)))

    assert sorted(results) == ["INVALID_QUANTITY", "OK"]
    with factory() as verification_session:
        assert VoyageService(verification_session).remaining_quantity(voyage.id) == 40
        assert len(ExitService(verification_session).list()) == 1


def test_exit_rejects_allocation_sum_mismatch_without_writing_transaction(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    voyage = _create_voyage(
        initialized_db_session,
        slot.id,
        entry_quantity=100,
    )

    with pytest.raises(DomainError) as raised:
        ExitService(initialized_db_session).create(
            ExitCreate(
                symbol="510300",
                exit_time=EXIT_TIME,
                exit_price=Decimal("4.100"),
                total_quantity=100,
                total_fee=Decimal("2"),
                allocations=[
                    ExitAllocationInput(voyage_id=voyage.id, quantity=99)
                ],
            )
        )

    assert raised.value.code == "INVALID_ALLOCATION"
    assert initialized_db_session.scalar(
        select(ExitTransaction.id).limit(1)
    ) is None
    assert VoyageService(initialized_db_session).remaining_quantity(voyage.id) == 100
    assert VoyageService(initialized_db_session).get(voyage.id).status == VoyageStatus.OPEN
    assert initialized_db_session.get(CapitalSlot, slot.id).status == SlotStatus.OCCUPIED


def test_voyage_number_is_not_reused_after_deleted_history(
    initialized_db_session: Session,
) -> None:
    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    service = VoyageService(initialized_db_session)
    first = _create_voyage(initialized_db_session, slot.id)
    first_number = first.voyage_no
    service.cancel(first.id)
    initialized_db_session.delete(first)
    initialized_db_session.commit()

    second = _create_voyage(initialized_db_session, slot.id)

    assert first_number == "QC-0001"
    assert second.voyage_no == "QC-0002"


def test_sqlite_enables_wal_and_enforces_foreign_keys(
    initialized_db_session: Session,
    db_engine: Engine,
) -> None:
    with db_engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    _create_security(initialized_db_session)
    slot = _slots(initialized_db_session)[0]
    _create_voyage(initialized_db_session, slot.id)

    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.exec_driver_sql(
                f"DELETE FROM {CapitalSlot.__tablename__} WHERE id = ?",
                (slot.id,),
            )
