"""Adapter interfaces and provider scaffolds for FinCouncil data sources.

Adapters return raw provider output. Normalization into canonical
``PriceRecord`` / ``FundamentalsRecord`` objects happens in
``fincouncil.data.normalize``.
"""

from fincouncil.data.adapters.base import BaseAdapter
from fincouncil.data.adapters.openbb import OpenBBAdapter, OpenBBAdapterError, OpenBBUnavailableError
from fincouncil.data.adapters.yfinance import YFinanceAdapter, YFinanceAdapterError, YFinanceUnavailableError
from fincouncil.data.adapters.finnhub import FinnhubAdapter, FinnhubAdapterError, FinnhubUnavailableError
from fincouncil.data.adapters.fred import FREDAdapter, FREDAdapterError, FREDUnavailableError
from fincouncil.data.adapters.akshare import AkShareAdapter, AkShareAdapterError, AkShareUnavailableError
from fincouncil.data.adapters.tushare import TushareAdapter, PaidProviderNotEnabledError

__all__ = [
    "BaseAdapter",
    "OpenBBAdapter",
    "OpenBBAdapterError",
    "OpenBBUnavailableError",
    "YFinanceAdapter",
    "YFinanceAdapterError",
    "YFinanceUnavailableError",
    "FinnhubAdapter",
    "FinnhubAdapterError",
    "FinnhubUnavailableError",
    "FREDAdapter",
    "FREDAdapterError",
    "FREDUnavailableError",
    "AkShareAdapter",
    "AkShareAdapterError",
    "AkShareUnavailableError",
    "TushareAdapter",
    "PaidProviderNotEnabledError",
]
