from __future__ import annotations

from app.market.base import MarketProvider
from app.market.models import Quote


class FallbackMarketProvider(MarketProvider):
    """Use the primary source first, then fill missing symbols from fallback."""

    def __init__(self, primary: MarketProvider, fallback: MarketProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def get_quotes(self, symbols: set[str]) -> dict[str, Quote]:
        try:
            quotes = self.primary.get_quotes(symbols)
        except Exception as primary_error:
            try:
                return self.fallback.get_quotes(symbols)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"all market providers failed: primary={primary_error}; fallback={fallback_error}"
                ) from fallback_error

        missing = symbols.difference(quotes)
        if not missing:
            return quotes
        try:
            return {**quotes, **self.fallback.get_quotes(missing)}
        except Exception:
            # A valid primary quote remains useful even if the fallback is down.
            return quotes
