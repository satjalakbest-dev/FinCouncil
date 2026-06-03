"""Canonical record schemas for the FinCouncil data layer.

All financial data flowing through the system MUST conform to one of these
schemas.  No field may be absent — if a provider does not supply it, the
normalizer fills ``None`` with a documented reason.

Design reference: PHASE1_DATA_LAYER_SPRINT.md T1.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

class RecordType(str, Enum):
    PRICE = "price"
    FUNDAMENTALS = "fundamentals"
    SYMBOL = "symbol"
    RECONCILE_LOG = "reconcile_log"


@dataclass(frozen=True)
class SourceTag:
    """Provenance tag attached to every canonical record."""

    provider: str          # e.g. "openbb", "yfinance", "alpha_vantage"
    fetched_at: datetime   # when the adapter actually fetched the data


@dataclass(frozen=True)
class CanonicalRecord:
    """Base record — every concrete record inherits from this.

    Invariants enforced by the normalizer:
    - ``source`` is always present.
    - ``currency`` is a 3-letter ISO-4217 code.
    - ``as_of`` is the reference date (not the fetch timestamp).
    """

    record_type: RecordType
    symbol: str            # canonical ``{exchange}:{ticker}``, e.g. "NYSE:AAPL"
    source: SourceTag
    currency: str          # ISO-4217, e.g. "USD", "JPY", "THB", "HKD"
    as_of: date


# ---------------------------------------------------------------------------
# Price record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PriceRecord(CanonicalRecord):
    """EOD (end-of-day) price bar.

    All monetary values are in ``currency`` units.
    ``adjusted_close`` accounts for splits and dividends; the normalizer
    MUST document whether it uses the provider's adjustment or computes
    its own (PHASE1 gotcha: adjusted vs raw close).
    """

    record_type: RecordType = field(default=RecordType.PRICE, init=False)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    adjusted_close: Optional[float] = None


# ---------------------------------------------------------------------------
# Fundamentals record
# ---------------------------------------------------------------------------

class FiscalPeriod(str, Enum):
    FY = "FY"   # full year
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


@dataclass(frozen=True)
class FundamentalsRecord(CanonicalRecord):
    """Fundamental financial data for one period.

    ``line_items`` is a flat dict of named values (e.g.
    ``{"revenue": 1_000_000, "net_income": 200_000, ...}``).
    ``ratios`` holds computed ratios (PE, ROE, etc.).
    All monetary values are in ``currency`` units.
    """

    record_type: RecordType = field(default=RecordType.FUNDAMENTALS, init=False)
    period: FiscalPeriod = FiscalPeriod.FY
    fiscal_date: Optional[date] = None
    line_items: dict[str, Any] = field(default_factory=dict)
    ratios: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Symbol mapping record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SymbolRecord(CanonicalRecord):
    """Mapping between canonical symbol and provider-specific ticker.

    ``provider_ticker`` is what you pass to the provider API
    (e.g. ``"7011.T"`` for Yahoo/OpenBB Japan, ``"PTT.BK"`` for Thai).
    """

    record_type: RecordType = field(default=RecordType.SYMBOL, init=False)
    exchange: str               # e.g. "NYSE", "SET", "TSE", "HKEX", "SSE"
    provider_ticker: str        # e.g. "AAPL", "7011.T", "PTT.BK", "00700.HK"
    security_name: str = ""
    asset_type: str = ""        # "equity", "etf", "adr", ...


# ---------------------------------------------------------------------------
# Reconcile log record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReconcileResult:
    """Output of a single reconcile comparison.

    ``flagged`` is True when the percentage diff exceeds the threshold.
    ``explanation`` documents *why* the diff occurred (or why it is
    acceptable, e.g. "adjusted_close vs raw close").
    """

    symbol: str
    field: str
    as_of: date
    currency: str
    values: dict[str, float]        # provider -> value
    diff_pct: Optional[float]       # |max - min| / mean * 100
    flagged: bool
    explanation: str = ""


@dataclass(frozen=True)
class ReconcileLog(CanonicalRecord):
    """Persisted reconcile comparison record (stored in DuckDB).

    ``results`` contains one entry per provider pair comparison.
    """

    record_type: RecordType = field(default=RecordType.RECONCILE_LOG, init=False)
    results: list[ReconcileResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reconcile thresholds (from DATA_SOURCES.md)
# ---------------------------------------------------------------------------

RECONCILE_THRESHOLD_PRICE_PCT = 0.5   # EOD price: 0.5%
RECONCILE_THRESHOLD_FUNDAMENTALS_PCT = 1.0  # Fundamentals: 1%
