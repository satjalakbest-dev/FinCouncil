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


def test_price_record_requires_audit_fields_and_ohlcv_contract() -> None:
    record = PriceRecord(
        symbol="NASDAQ:AAPL",
        date=date(2026, 6, 1),
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        volume=100,
        adjusted_close=Decimal("11"),
        source="openbb:yfinance",
        currency=CurrencyCode("USD"),
        as_of=date(2026, 6, 2),
    )

    validate_record(record)


def test_price_record_rejects_missing_currency_contract() -> None:
    record = PriceRecord(
        symbol="SET:PTT",
        date=date(2026, 6, 1),
        open=Decimal("30"),
        high=Decimal("31"),
        low=Decimal("29"),
        close=Decimal("30.5"),
        volume=100,
        adjusted_close=Decimal("30.5"),
        source="openbb:yfinance",
        currency=CurrencyCode("thb"),
        as_of=date(2026, 6, 2),
    )

    with pytest.raises(ValidationError, match="currency"):
        validate_record(record)


def test_fundamentals_record_covers_period_fiscal_date_statements_and_ratios() -> None:
    record = FundamentalsRecord(
        symbol="NASDAQ:AAPL",
        period=Period.FY,
        fiscal_date=date(2025, 9, 30),
        revenue=Decimal("1000000"),
        net_income=Decimal("200000"),
        total_assets=Decimal("5000000"),
        eps=Decimal("6.00"),
        pe_ratio=Decimal("30.0"),
        roe=Decimal("0.25"),
        source="openbb:fmp",
        currency=CurrencyCode("USD"),
        as_of=date(2026, 6, 2),
    )

    validate_record(record)


def test_fundamentals_record_rejects_empty_statement_shell() -> None:
    record = FundamentalsRecord(
        symbol="NASDAQ:AAPL",
        period=Period.Q,
        fiscal_date=date(2026, 3, 31),
        pe_ratio=Decimal("30.0"),
        source="openbb:fmp",
        currency=CurrencyCode("USD"),
        as_of=date(2026, 6, 2),
    )

    with pytest.raises(ValidationError, match="core statement"):
        validate_record(record)


def test_symbol_record_uses_exchange_ticker_convention_and_provider_mapping() -> None:
    record = SymbolRecord(
        symbol="TSE:7011",
        exchange="TSE",
        ticker="7011",
        provider_symbols={"yfinance": "7011.T", "jquants": "7011"},
        name="Sample issuer",
        country="JP",
        source="manual-fixture",
        currency=CurrencyCode("JPY"),
        as_of=date(2026, 6, 2),
    )

    validate_record(record)


def test_reconcile_log_requires_two_sources_and_flag_explanation() -> None:
    record = ReconcileLogRecord(
        symbol="NASDAQ:AAPL",
        field="close",
        date=date(2026, 6, 1),
        values={"openbb": Decimal("100"), "stooq": Decimal("101")},
        diff_pct=Decimal("1.0"),
        threshold_pct=Decimal("0.5"),
        status=ReconcileStatus.FLAG,
        explanation="Injected discrepancy exceeded threshold.",
        source="fincouncil.reconcile:v1",
        currency=CurrencyCode("USD"),
        as_of=date(2026, 6, 2),
    )

    validate_record(record)
