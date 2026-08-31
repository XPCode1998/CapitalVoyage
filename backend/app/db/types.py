from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.types import String, TypeDecorator


class DecimalType(TypeDecorator[Decimal]):
    """Losslessly stores Decimal values as canonical strings in SQLite."""

    impl = String(80)
    cache_ok = True

    def process_bind_param(self, value: Decimal | str | int | None, dialect):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
            raise TypeError("DecimalType accepts only Decimal, str, int, or None")
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite():
            raise ValueError("DecimalType requires a finite decimal value")
        return format(decimal_value, "f")

    def process_result_value(self, value: str | None, dialect):
        if value is None:
            return None
        decimal_value = Decimal(value)
        if not decimal_value.is_finite():
            raise ValueError("stored decimal value must be finite")
        return decimal_value


class AwareDateTime(TypeDecorator[datetime]):
    """Preserves timezone offsets even when SQLite is used."""

    impl = String(48)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone-aware datetime required")
        return value.isoformat()

    def process_result_value(self, value: str | None, dialect):
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("stored datetime must be timezone-aware")
        return parsed
