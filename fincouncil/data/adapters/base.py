"""Abstract base adapter — contract for all data providers.

Concrete adapters (OpenBB, yfinance, etc.) must implement these methods.
The normalizer layer consumes adapter output; nothing else talks to
providers directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional


class BaseAdapter(ABC):
    """Interface that every data source adapter must implement.

    Adapters return **raw** provider output ( dicts, DataFrames, etc.).
    Normalization to canonical schema happens in the normalize layer,
    not here.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider name (e.g. ``"openbb"``, ``"yfinance"``)."""

    @abstractmethod
    def get_price(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """Fetch EOD price bars for *symbol* in the given date range.

        Returns a list of dicts with at minimum: date, open, high, low,
        close, volume.  The normalizer will convert these to
        ``PriceRecord`` objects.
        """

    @abstractmethod
    def get_fundamentals(
        self,
        symbol: str,
        period: str = "FY",
    ) -> list[dict[str, Any]]:
        """Fetch fundamental data for *symbol*.

        Returns a list of dicts with line items and ratios.
        The normalizer will convert these to ``FundamentalsRecord`` objects.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the provider is reachable and credentials (if
        needed) are present.

        Used by the test harness to skip live tests when credentials
        are missing (CP0 credential blocker).
        """
