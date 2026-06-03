"""Schema validation tests — verify canonical record contracts.

These tests ensure the schema dataclasses enforce the invariants
required by CP1/T1.1: every record has source + currency + as_of.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from fincouncil.data.schema import (
    CanonicalRecord,
    FiscalPeriod,
    FundamentalsRecord,
    PriceRecord,
    RecordType,
    ReconcileResult,
    SourceTag,
    SymbolRecord,
)


class TestSourceTag:
    """SourceTag must carry provider name and fetch timestamp."""

    def test_create_source_tag(self) -> None:
        tag = SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2))
        assert tag.provider == "openbb"
        assert tag.fetched_at.year == 2026

    def test_source_tag_is_frozen(self) -> None:
        tag = SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2))
        with pytest.raises(AttributeError):
            tag.provider = "yfinance"  # type: ignore[misc]


class TestPriceRecord:
    """PriceRecord must satisfy the canonical record contract."""

    def test_price_record_has_all_fields(self) -> None:
        rec = PriceRecord(
            symbol="NASDAQ:AAPL",
            source=SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2)),
            currency="USD",
            as_of=date(2026, 6, 2),
            open=195.0,
            high=196.0,
            low=194.0,
            close=195.5,
            volume=50_000_000,
            adjusted_close=195.5,
        )
        assert rec.record_type == RecordType.PRICE
        assert rec.symbol == "NASDAQ:AAPL"
        assert rec.currency == "USD"
        assert rec.close == 195.5
        assert rec.source.provider == "openbb"

    def test_price_record_is_frozen(self) -> None:
        rec = PriceRecord(
            symbol="NASDAQ:AAPL",
            source=SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2)),
            currency="USD",
            as_of=date(2026, 6, 2),
        )
        with pytest.raises(AttributeError):
            rec.close = 200.0  # type: ignore[misc]

    def test_price_record_defaults_to_none(self) -> None:
        """Optional OHLCV fields default to None when not provided."""
        rec = PriceRecord(
            symbol="NASDAQ:AAPL",
            source=SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2)),
            currency="USD",
            as_of=date(2026, 6, 2),
        )
        assert rec.open is None
        assert rec.high is None
        assert rec.low is None
        assert rec.close is None
        assert rec.volume is None
        assert rec.adjusted_close is None


class TestFundamentalsRecord:
    def test_fundamentals_record_creation(self) -> None:
        rec = FundamentalsRecord(
            symbol="NASDAQ:AAPL",
            source=SourceTag(provider="openbb", fetched_at=datetime(2026, 6, 2)),
            currency="USD",
            as_of=date(2026, 6, 2),
            period=FiscalPeriod.FY,
            fiscal_date=date(2025, 9, 27),
            line_items={"revenue": 391e9},
            ratios={"pe_ratio": 33.0},
        )
        assert rec.record_type == RecordType.FUNDAMENTALS
        assert rec.period == FiscalPeriod.FY
        assert rec.line_items["revenue"] == 391e9


class TestReconcileThresholds:
    """Verify threshold constants match the spec."""

    def test_price_threshold(self) -> None:
        from fincouncil.data.schema import RECONCILE_THRESHOLD_PRICE_PCT
        assert RECONCILE_THRESHOLD_PRICE_PCT == 0.5

    def test_fundamentals_threshold(self) -> None:
        from fincouncil.data.schema import RECONCILE_THRESHOLD_FUNDAMENTALS_PCT
        assert RECONCILE_THRESHOLD_FUNDAMENTALS_PCT == 1.0
