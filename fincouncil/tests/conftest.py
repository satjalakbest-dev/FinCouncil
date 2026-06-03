"""Shared test fixtures and credential guard for FinCouncil test suite.

CP0 credential blocker policy (from P0_READINESS.md):
- No fabricated financial output in production code paths.
- No live provider validation unless credentials exist in the environment.
- Tests that need live providers are marked with ``@pytest.mark.live``
  and auto-skip when credentials are absent.
- Unit tests use synthetic fixtures clearly labeled as test data.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from fincouncil.data.schema import (
    CurrencyCode,
    FundamentalsRecord,
    Period,
    PriceRecord,
    ReconcileLogRecord,
    ReconcileStatus,
)


# ---------------------------------------------------------------------------
# Credential guard — auto-skip live tests when keys are absent
# ---------------------------------------------------------------------------

CREDENTIAL_ENV_VARS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "ZHIPU_API_KEY",
    "DASHSCOPE_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "FINNHUB_API_KEY",
    "FMP_API_KEY",
]


def has_any_provider_credential() -> bool:
    """Return True if at least one provider API key is set."""
    return any(os.getenv(v) for v in CREDENTIAL_ENV_VARS)


# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------

def pytest_configure(config: Any) -> None:
    """Register the ``live`` marker."""
    config.addinivalue_line(
        "markers", "live: requires live provider credentials (auto-skip)"
    )


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Auto-skip ``live`` tests when no provider credentials are present."""
    if has_any_provider_credential():
        return
    skip_live = pytest.mark.skip(reason="No provider credentials in environment")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _currency(code: str) -> CurrencyCode:
    return CurrencyCode(code)


# ---------------------------------------------------------------------------
# Synthetic test fixtures — clearly NOT real financial data
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_price_aapl() -> PriceRecord:
    """Synthetic AAPL price record — **test fixture, not real data**."""
    return PriceRecord(
        source="openbb",
        currency=_currency("USD"),
        as_of=date(2026, 6, 2),
        symbol="NASDAQ:AAPL",
        date=date(2026, 6, 2),
        open=Decimal("195.00"),
        high=Decimal("196.50"),
        low=Decimal("194.80"),
        close=Decimal("195.50"),
        volume=50_000_000,
        adjusted_close=Decimal("195.50"),
    )


@pytest.fixture
def synthetic_price_ptt() -> PriceRecord:
    """Synthetic PTT.BK price record — **test fixture, not real data**."""
    return PriceRecord(
        source="openbb",
        currency=_currency("THB"),
        as_of=date(2026, 6, 2),
        symbol="SET:PTT",
        date=date(2026, 6, 2),
        open=Decimal("32.50"),
        high=Decimal("32.75"),
        low=Decimal("32.25"),
        close=Decimal("32.60"),
        volume=15_000_000,
        adjusted_close=Decimal("32.60"),
    )


@pytest.fixture
def synthetic_price_00700() -> PriceRecord:
    """Synthetic 00700.HK price record — **test fixture, not real data**."""
    return PriceRecord(
        source="openbb",
        currency=_currency("HKD"),
        as_of=date(2026, 6, 2),
        symbol="HKEX:00700",
        date=date(2026, 6, 2),
        open=Decimal("480.00"),
        high=Decimal("485.00"),
        low=Decimal("478.50"),
        close=Decimal("483.00"),
        volume=12_000_000,
        adjusted_close=Decimal("483.00"),
    )


@pytest.fixture
def synthetic_fundamentals_aapl() -> FundamentalsRecord:
    """Synthetic AAPL fundamentals — **test fixture, not real data**."""
    return FundamentalsRecord(
        source="openbb",
        currency=_currency("USD"),
        as_of=date(2026, 6, 2),
        symbol="NASDAQ:AAPL",
        period=Period.FY,
        fiscal_date=date(2025, 9, 27),
        revenue=Decimal("391000000000"),
        net_income=Decimal("94000000000"),
        total_assets=Decimal("365000000000"),
        shareholders_equity=Decimal("62000000000"),
        eps=Decimal("6.11"),
        pe_ratio=Decimal("33.0"),
        roe=Decimal("1.52"),
    )
