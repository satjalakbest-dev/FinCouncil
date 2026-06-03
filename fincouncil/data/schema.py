"""Canonical FinCouncil data-layer record contracts.

The Phase 1 data layer intentionally starts with dependency-free runtime
contracts so adapters, normalization, storage, reconcile, MCP, and the later
TradingAgents shim can agree on field names before provider code exists.
Every public record carries source, currency, and as_of for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Mapping, NewType, Sequence

CurrencyCode = NewType("CurrencyCode", str)
RecordKind = Literal["price", "fundamentals", "symbol", "reconcile_log"]


class ValidationError(ValueError):
    """Raised when a canonical record violates the Phase 1 contract."""


class Period(str, Enum):
    """Supported financial statement periods."""

    FY = "FY"
    Q = "Q"


class ReconcileStatus(str, Enum):
    """Reconcile outcome status."""

    PASS = "PASS"
    FLAG = "FLAG"


@dataclass(frozen=True, kw_only=True)
class SourceStampedRecord:
    """Common audit fields required on every canonical record."""

    source: str
    currency: CurrencyCode
    as_of: date | datetime

    def validate_common(self) -> None:
        _require_non_empty("source", self.source)
        _validate_currency(self.currency)
        _validate_temporal("as_of", self.as_of)


@dataclass(frozen=True, kw_only=True)
class PriceRecord(SourceStampedRecord):
    """Canonical end-of-day OHLCV price record.

    Field units:
    - open/high/low/close/adjusted_close: quoted in ``currency``.
    - volume: provider-reported share/unit count for that trading date.
    """

    kind: Literal["price"] = "price"
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal

    def validate(self) -> None:
        self.validate_common()
        _require_non_empty("symbol", self.symbol)
        _validate_temporal("date", self.date)
        for field_name in ("open", "high", "low", "close", "adjusted_close"):
            _validate_decimal(field_name, getattr(self, field_name), minimum=Decimal("0"))
        if self.volume < 0:
            raise ValidationError("volume must be non-negative")
        if self.low > self.high:
            raise ValidationError("low must be less than or equal to high")
        for field_name in ("open", "close", "adjusted_close"):
            value = getattr(self, field_name)
            if value < self.low or value > self.high:
                raise ValidationError(f"{field_name} must fall within low/high")


@dataclass(frozen=True, kw_only=True)
class FundamentalsRecord(SourceStampedRecord):
    """Canonical financial statement and ratio record.

    Statement values are quoted in ``currency`` unless the field name denotes a
    per-share value or ratio. Optional fields allow market/provider differences,
    but each record must contain at least one core statement value so downstream
    valuation never treats an empty shell as real data.
    """

    kind: Literal["fundamentals"] = "fundamentals"
    symbol: str
    period: Period
    fiscal_date: date
    revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    operating_income: Decimal | None = None
    net_income: Decimal | None = None
    total_assets: Decimal | None = None
    total_liabilities: Decimal | None = None
    shareholders_equity: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    capital_expenditure: Decimal | None = None
    free_cash_flow: Decimal | None = None
    eps: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    roe: Decimal | None = None
    debt_to_equity: Decimal | None = None

    def validate(self) -> None:
        self.validate_common()
        _require_non_empty("symbol", self.symbol)
        if not isinstance(self.period, Period):
            raise ValidationError("period must be Period.FY or Period.Q")
        _validate_temporal("fiscal_date", self.fiscal_date)
        populated_statement_fields = 0
        for field_name in _FUNDAMENTAL_DECIMAL_FIELDS:
            value = getattr(self, field_name)
            if value is not None:
                _validate_decimal(field_name, value)
                if field_name in _CORE_STATEMENT_FIELDS:
                    populated_statement_fields += 1
        if populated_statement_fields == 0:
            raise ValidationError("fundamentals must include at least one core statement value")


@dataclass(frozen=True, kw_only=True)
class SymbolRecord(SourceStampedRecord):
    """Canonical instrument identity and provider mapping record."""

    kind: Literal["symbol"] = "symbol"
    symbol: str
    exchange: str
    ticker: str
    provider_symbols: Mapping[str, str]
    name: str | None = None
    country: str | None = None
    asset_type: str = "equity"

    def validate(self) -> None:
        self.validate_common()
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("exchange", self.exchange)
        _require_non_empty("ticker", self.ticker)
        if ":" not in self.symbol:
            raise ValidationError("symbol must use {exchange}:{ticker} convention")
        symbol_exchange, symbol_ticker = self.symbol.split(":", 1)
        if symbol_exchange != self.exchange or symbol_ticker != self.ticker:
            raise ValidationError("symbol must match exchange and ticker fields")
        if not self.provider_symbols:
            raise ValidationError("provider_symbols must include at least one provider mapping")
        for provider, provider_symbol in self.provider_symbols.items():
            _require_non_empty("provider", provider)
            _require_non_empty(f"provider_symbols[{provider}]", provider_symbol)


@dataclass(frozen=True, kw_only=True)
class ReconcileLogRecord(SourceStampedRecord):
    """Canonical audit log for cross-source value comparison."""

    kind: Literal["reconcile_log"] = "reconcile_log"
    symbol: str
    field: str
    date: date
    values: Mapping[str, Decimal]
    diff_pct: Decimal
    threshold_pct: Decimal
    status: ReconcileStatus
    explanation: str

    def validate(self) -> None:
        self.validate_common()
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("field", self.field)
        _validate_temporal("date", self.date)
        if len(self.values) < 2:
            raise ValidationError("reconcile values must include at least two sources")
        for source, value in self.values.items():
            _require_non_empty("values source", source)
            _validate_decimal(f"values[{source}]", value)
        _validate_decimal("diff_pct", self.diff_pct, minimum=Decimal("0"))
        _validate_decimal("threshold_pct", self.threshold_pct, minimum=Decimal("0"))
        if not isinstance(self.status, ReconcileStatus):
            raise ValidationError("status must be ReconcileStatus.PASS or ReconcileStatus.FLAG")
        _require_non_empty("explanation", self.explanation)


CanonicalRecord = PriceRecord | FundamentalsRecord | SymbolRecord | ReconcileLogRecord

_CORE_STATEMENT_FIELDS = frozenset(
    {
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "total_assets",
        "total_liabilities",
        "shareholders_equity",
        "operating_cash_flow",
        "capital_expenditure",
        "free_cash_flow",
    }
)
_FUNDAMENTAL_DECIMAL_FIELDS = tuple(
    sorted(
        _CORE_STATEMENT_FIELDS
        | {"eps", "pe_ratio", "pb_ratio", "roe", "debt_to_equity"}
    )
)


def validate_record(record: CanonicalRecord) -> None:
    """Validate any canonical FinCouncil data-layer record."""

    if not isinstance(
        record, (PriceRecord, FundamentalsRecord, SymbolRecord, ReconcileLogRecord)
    ):
        raise ValidationError(f"unsupported canonical record type: {type(record)!r}")
    record.validate()


def validate_records(records: Sequence[CanonicalRecord]) -> None:
    """Validate a batch of canonical records."""

    for record in records:
        validate_record(record)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")


def _validate_currency(currency: CurrencyCode) -> None:
    value = str(currency)
    if len(value) != 3 or not value.isalpha() or value.upper() != value:
        raise ValidationError("currency must be an uppercase ISO-4217 code")


def _validate_temporal(field_name: str, value: date | datetime) -> None:
    if not isinstance(value, (date, datetime)):
        raise ValidationError(f"{field_name} must be a date or datetime")


def _validate_decimal(
    field_name: str,
    value: Any,
    *,
    minimum: Decimal | None = None,
) -> None:
    if not isinstance(value, Decimal):
        raise ValidationError(f"{field_name} must be Decimal")
    if not value.is_finite():
        raise ValidationError(f"{field_name} must be finite")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{field_name} must be >= {minimum}")
