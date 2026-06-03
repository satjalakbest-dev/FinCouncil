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
from datetime import date, datetime
from typing import Any

import pytest

from fincouncil.data.schema import (
    CanonicalRecord,
    FiscalPeriod,
    PriceRecord,
    FundamentalsRecord,
    SourceTag,
    SymbolRecord,
    ReconcileResult,
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


def requires_credentials(marker_name: str = "live") -> bool:
    """Check whether the required credential for a specific provider exists.

    This is a simple gate — individual tests can refine it.
    """
    return has_any_provider_credential()


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
# Synthetic test fixtures — clearly NOT real financial data
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_source_openbb() -> SourceTag:
    """Synthetic source tag — ``openbb`` provider, frozen timestamp."""
    return SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2, 20, 0, 0))


@pytest.fixture
def synthetic_source_yfinance() -> SourceTag:
    """Synthetic source tag — ``yfinance`` provider, frozen timestamp."""
    return SourceTag(provider="yfinance", fetched_at=datetime(2026, 6, 2, 20, 5, 0))


@pytest.fixture
def synthetic_price_aapl(synthetic_source_openbb: SourceTag) -> PriceRecord:
    """Synthetic AAPL price record — **test fixture, not real data**."""
    return PriceRecord(
        symbol="NASDAQ:AAPL",
        source=synthetic_source_openbb,
        currency="USD",
        as_of=date(2026, 6, 2),
        open=195.00,
        high=196.50,
        low=194.80,
        close=195.50,
        volume=50_000_000,
        adjusted_close=195.50,
    )


@pytest.fixture
def synthetic_price_ptt(synthetic_source_openbb: SourceTag) -> PriceRecord:
    """Synthetic PTT.BK price record — **test fixture, not real data**."""
    return PriceRecord(
        symbol="SET:PTT",
        source=synthetic_source_openbb,
        currency="THB",
        as_of=date(2026, 6, 2),
        open=32.50,
        high=32.75,
        low=32.25,
        close=32.60,
        volume=15_000_000,
        adjusted_close=32.60,
    )


@pytest.fixture
def synthetic_price_00700(synthetic_source_openbb: SourceTag) -> PriceRecord:
    """Synthetic 00700.HK price record — **test fixture, not real data**."""
    return PriceRecord(
        symbol="HKEX:00700",
        source=synthetic_source_openbb,
        currency="HKD",
        as_of=date(2026, 6, 2),
        open=480.00,
        high=485.00,
        low=478.50,
        close=483.00,
        volume=12_000_000,
        adjusted_close=483.00,
    )


@pytest.fixture
def synthetic_fundamentals_aapl(synthetic_source_openbb: SourceTag) -> FundamentalsRecord:
    """Synthetic AAPL fundamentals — **test fixture, not real data**."""
    return FundamentalsRecord(
        symbol="NASDAQ:AAPL",
        source=synthetic_source_openbb,
        currency="USD",
        as_of=date(2026, 6, 2),
        period=FiscalPeriod.FY,
        fiscal_date=date(2025, 9, 27),
        line_items={
            "revenue": 391_000_000_000,
            "net_income": 94_000_000_000,
            "total_assets": 365_000_000_000,
            "total_equity": 62_000_000_000,
        },
        ratios={
            "pe_ratio": 33.0,
            "roe": 1.52,
        },
    )
