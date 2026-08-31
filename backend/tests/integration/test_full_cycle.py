from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.capital.service import CapitalService
from app.core.enums import SettlementMode, SlotStatus, VoyageStatus
from app.exit.schemas import ExitAllocationInput, ExitCreate
from app.exit.service import ExitService
from app.market.cache import QuoteCache
from app.market.models import Quote
from app.return_engine.center import ReturnCenterService
from app.return_engine.fee import FeeCalculator
from app.return_engine.models import FeeConfig
from app.security.schemas import SecurityCreate
from app.security.service import SecurityService
from app.voyage.schemas import VoyageCreate
from app.voyage.service import VoyageService


TZ=ZoneInfo("Asia/Shanghai"); ENTRY=datetime(2026,8,28,10,0,tzinfo=TZ); NOW=datetime(2026,8,31,10,30,tzinfo=TZ)


def test_three_voyage_return_center_to_multi_allocation_exit(initialized_db_session):
    SecurityService(initialized_db_session).create(SecurityCreate(symbol="510300",name="沪深300ETF",settlement_mode=SettlementMode.T1))
    slots=CapitalService(initialized_db_session).list_slots(); voyages=[]
    for slot,price,qty in zip(slots,["4.000","3.900","3.850"],[12500,12800,12900]):
        voyages.append(VoyageService(initialized_db_session).create(VoyageCreate(slot_id=slot.id,symbol="510300",entry_time=ENTRY,entry_price=Decimal(price),entry_quantity=qty,entry_fee=Decimal("0"),target_return=Decimal("0.02"),sellable_at=NOW)))
    cache=QuoteCache(30); cache.set(Quote(symbol="510300",name="沪深300ETF",last_price=Decimal("3.990"),bid1=Decimal("3.990"),ask1=Decimal("3.991"),quote_time=NOW,received_at=NOW,source="mock"))
    groups=ReturnCenterService(initialized_db_session,cache,fee_calculator=FeeCalculator(FeeConfig()),now_factory=lambda:NOW).get_ready()
    assert groups[0].ready_quantity==25700
    ExitService(initialized_db_session).create(ExitCreate(symbol="510300",exit_time=NOW,exit_price=Decimal("3.990"),total_quantity=25700,total_fee=Decimal("0"),allocations=[ExitAllocationInput(voyage_id=voyages[1].id,quantity=12800),ExitAllocationInput(voyage_id=voyages[2].id,quantity=12900)]))
    assert VoyageService(initialized_db_session).get(voyages[0].id).status==VoyageStatus.OPEN
    assert VoyageService(initialized_db_session).remaining_quantity(voyages[0].id)==12500
    assert all(VoyageService(initialized_db_session).get(v.id).status==VoyageStatus.CLOSED for v in voyages[1:])
    assert all(initialized_db_session.get(type(slots[0]),s.id).status==SlotStatus.AVAILABLE for s in slots[1:3])

