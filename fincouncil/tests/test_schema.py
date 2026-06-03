"""Schema validation tests — verify canonical record contracts.

These tests ensure the schema dataclasses enforce the invariants
required by CP1/T1.1: every record has source + currency + as_of.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from fincouncil.data.schema import (
    CurrencyCode,
    FundamentalsRecord,
    Period,
    PriceRecord,
    ReconcileLogRecord,
    ReconcileStatus,
    SymbolRecord,
    ValidationError,
    validate_record,
)


def _currency(code: str) -> CurrencyCode:
    return CurrencyCode(code)


class TestPriceRecord:
    """PriceRecord must satisfy the canonical record contract."""

    def test_price_record_creation(self) -> None:
        rec = PriceRecord(
            source="openbb",
            currency=_currency("USD"),
            as_of=date(2026, 6, 2),
            symbol="NASDAQ:AAPL",
            date=date(2026, 6, 2),
            open=Decimal("195.00"),
            high=Decimal("196.00"),
            low=Decimal("194.00"),
            close=Decimal("195.50"),
            volume=50_000_000,
            adjusted_close=Decimal("195.50"),
        )
        assert rec.kind == "price"
        assert rec.symbol == "NASDAQ:AAPL"
        assert rec.currency == "USD"
        assert rec.close == Decimal("195.50")
        assert rec.source == "openbb"

    def test_price_record_is_frozen(self) -> None:
        rec = PriceRecord(
            source="openbb",
            currency=_currency("USD"),
            as_of=date(2026, 6, 2),
            symbol="NASDAQ:AAPL",
            date=date(2026, 6, 2),
            open=Decimal("195.00"),
            high=Decimal("196.00"),
            low=Decimal("194.00"),
            close=Decimal("195.50"),
            volume=50_000_000,
            adjusted_close=Decimal("195.50"),
        )
        with pytest.raises(AttributeError):
            rec.close = Decimal("200.0")  # type: ignore[misc]

    def test_price_record_validates(self) -> None:
        rec = PriceRecord(
            source="openbb",
            currency=_currency("USD"),
            as_of=date(2026, 6, 2),
            symbol="NASDAQ:AAPL",
            date=date(2026, 6, 2),
            open=Decimal("195.00"),
            high=Decimal("196.00"),
            low=Decimal("194.00"),
            close=Decimal("195.50"),
            volume=50_000_000,
            adjusted_close=Decimal("195.50"),
        )
        validate_record(rec)  # must not raise

    def test_price_record_rejects_invalid_currency(self) -> None:
        with pytest.raises(ValidationError):
            PriceRecord(
                source="openbb",
                currency=_currency("XXX"),  # not in PHASE1_CURRENCY_CODES
                as_of=date(2026, 6, 2),
                symbol="NASDAQ:AAPL",
                date=date(2026, 6, 2),
                open=Decimal("195.00"),
                high=Decimal("196.00"),
                low=Decimal("194.00"),
                close=Decimal("195.50"),
                volume=50_000_000,
                adjusted_close=Decimal("195.50"),
            )

    def test_price_record_rejects_low_above_high(self) -> None:
        with pytest.raises(ValidationError):
            PriceRecord(
                source="openbb",
                currency=_currency("USD"),
                as_of=date(2026, 6, 2),
                symbol="NASDAQ:AAPL",
                date=date(2026, 6, 2),
                open=Decimal("195.00"),
                high=Decimal("194.00"),  # high < low
                low=Decimal("195.00"),
                close=Decimal("195.00"),
                volume=50_000_000,
                adjusted_close=Decimal("195.00"),
            )


class TestFundamentalsRecord:
    def test_fundamentals_record_creation(self) -> None:
        rec = FundamentalsRecord(
            source="openbb",
            currency=_currency("USD"),
            as_of=date(2026, 6, 2),
            symbol="NASDAQ:AAPL",
            period=Period.FY,
            fiscal_date=date(2025, 9, 27),
            revenue=Decimal("391000000000"),
            pe_ratio=Decimal("33.0"),
        )
        assert rec.kind == "fundamentals"
        assert rec.period == Period.FY
        assert rec.revenue == Decimal("391000000000")

    def test_fundamentals_requires_at_least_one_statement_field(self) -> None:
        with pytest.raises(ValidationError):
            FundamentalsRecord(
                source="openbb",
                currency=_currency("USD"),
                as_of=date(2026, 6, 2),
                symbol="NASDAQ:AAPL",
                period=Period.FY,
                fiscal_date=date(2025, 9, 27),
                # no core statement fields populated
                pe_ratio=Decimal("33.0"),
            )


class TestReconcileThresholds:
    """Verify threshold constants match the spec."""

    def test_price_threshold(self) -> None:
        from fincouncil.data.reconcile.engine import DEFAULT_PRICE_THRESHOLD_PCT
        assert DEFAULT_PRICE_THRESHOLD_PCT == Decimal("0.5")

    def test_fundamentals_threshold(self) -> None:
        from fincouncil.data.reconcile.engine import DEFAULT_FUNDAMENTALS_THRESHOLD_PCT
        assert DEFAULT_FUNDAMENTALS_THRESHOLD_PCT == Decimal("1.0")
