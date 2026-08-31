from __future__ import annotations

from abc import ABC, abstractmethod

from app.market.models import Quote


class MarketProvider(ABC):
    @abstractmethod
    def get_quotes(self, symbols: set[str]) -> dict[str, Quote]:
        """Return the available quotes for the requested security symbols."""

