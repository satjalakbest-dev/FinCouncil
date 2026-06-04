"""Shared test fixtures and credential guard for FinCouncil test suite.

CP0 credential blocker policy (from P0_READINESS.md):
- No fabricated financial output in production code paths.
- Live provider tests must be explicitly marked with ``@pytest.mark.live``.
- Credentialed providers auto-skip when credentials are absent.
- No-key providers use provider-specific opt-ins; yfinance live tests must also
  be marked ``@pytest.mark.yfinance`` and require ``YFINANCE_LIVE=1``.
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
# Live-test guards — keep default pytest hermetic
# ---------------------------------------------------------------------------

YFINANCE_LIVE_ENV = "YFINANCE_LIVE"
YFINANCE_LIVE_SKIP_REASON = "Set YFINANCE_LIVE=1 to run yfinance live tests"
YFINANCE_MARKER_CONTRACT_SKIP_REASON = (
    "yfinance live tests require both @pytest.mark.live and @pytest.mark.yfinance"
)
MISSING_CREDENTIALS_SKIP_REASON = "No provider credentials in environment"

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

def yfinance_live_enabled() -> bool:
    """Return True only when yfinance live tests are explicitly enabled."""
    return os.getenv(YFINANCE_LIVE_ENV) == "1"


def pytest_configure(config: Any) -> None:
    """Register live-provider markers used by the suite."""
    config.addinivalue_line(
        "markers",
        "live: requires an explicit live-provider opt-in or provider credentials",
    )
    config.addinivalue_line(
        "markers",
        "yfinance: yfinance-specific live provider test; requires YFINANCE_LIVE=1",
    )


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Auto-skip live tests unless their provider-specific gate is open.

    Credentialed providers keep the historical ``@pytest.mark.live`` behavior:
    they run only when at least one provider credential is present.  yfinance is
    intentionally different because it has no API key; unrelated credentials
    must not enable yfinance network tests.
    """
    skip_missing_credentials = pytest.mark.skip(reason=MISSING_CREDENTIALS_SKIP_REASON)
    skip_yfinance = pytest.mark.skip(reason=YFINANCE_LIVE_SKIP_REASON)
    has_credentials = has_any_provider_credential()
    run_yfinance_live = yfinance_live_enabled()

    skip_yfinance_marker_contract = pytest.mark.skip(
        reason=YFINANCE_MARKER_CONTRACT_SKIP_REASON
    )

    for item in items:
        is_live = "live" in item.keywords
        is_yfinance_marked = "yfinance" in item.keywords
        is_yfinance_file = "yfinance" in str(getattr(item, "nodeid", ""))

        if is_yfinance_marked and not is_live:
            item.add_marker(skip_yfinance_marker_contract)
            continue

        if is_live and is_yfinance_file and not is_yfinance_marked:
            item.add_marker(skip_yfinance_marker_contract)
            continue

        if not is_live:
            continue

        if is_yfinance_marked:
            if not run_yfinance_live:
                item.add_marker(skip_yfinance)
            continue

        if not has_credentials:
            item.add_marker(skip_missing_credentials)


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
