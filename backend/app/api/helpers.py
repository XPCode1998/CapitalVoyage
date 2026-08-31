from __future__ import annotations

from app.return_engine.monitor import MonitorState
from app.voyage.models import Voyage


def voyage_dict(voyage: Voyage, monitor: MonitorState | None = None) -> dict:
    return {
        "id": voyage.id,
        "voyage_no": voyage.voyage_no,
        "slot_id": voyage.slot_id,
        "symbol": voyage.symbol,
        "name": voyage.security.name if voyage.security else voyage.symbol,
        "entry_time": voyage.entry_time,
        "entry_price": voyage.entry_price,
        "entry_quantity": voyage.entry_quantity,
        "entry_fee": voyage.entry_fee,
        "entry_cost": voyage.entry_cost,
        "target_return": voyage.target_return,
        "sellable_at": voyage.sellable_at,
        "status": voyage.status,
        "remaining_quantity": voyage.remaining_quantity,
        "first_target_reached_at": voyage.first_target_reached_at,
        "last_target_reached_at": voyage.last_target_reached_at,
        "runtime_state": monitor.runtime_state if monitor else "QUOTE_STALE",
        "monitor_price": monitor.last_price if monitor else None,
        "net_return": monitor.last_return_rate if monitor else None,
        "quote_time": monitor.last_quote_time if monitor else None,
        "created_at": voyage.created_at,
        "updated_at": voyage.updated_at,
    }

