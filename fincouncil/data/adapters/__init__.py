"""Adapter interfaces and provider scaffolds for FinCouncil data sources.

Adapters return raw provider output. Normalization into canonical
``PriceRecord`` / ``FundamentalsRecord`` objects happens in
``fincouncil.data.normalize``.
"""

from fincouncil.data.adapters.base import BaseAdapter
from fincouncil.data.adapters.openbb import OpenBBAdapter, OpenBBAdapterError, OpenBBUnavailableError
from fincouncil.data.adapters.yfinance import YFinanceAdapter, YFinanceAdapterError, YFinanceUnavailableError

__all__ = [
    "BaseAdapter",
    "OpenBBAdapter",
    "OpenBBAdapterError",
    "OpenBBUnavailableError",
    "YFinanceAdapter",
    "YFinanceAdapterError",
    "YFinanceUnavailableError",
]
