"""Synthetic T1.6 normalization fixtures.

These tests use mocked adapter payloads only. They do not call live providers
and do not encode production market facts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from fincouncil.data.normalize import (
    NormalizationError,
    normalize_price_record,
    normalize_price_records,
)
from fincouncil.data.schema import PriceRecord, validate_record


def synthetic_raw_price(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date": "2026-01-05T00:00:00Z",
        "open": "10.00",
        "high": "11.00",
        "low": "9.50",
        "close": "10.50",
        "volume": "12345",
    }
    row.update(overrides)
    return row


def test_normalize_price_adds_audit_fields_and_validates_schema() -> None:
    record = normalize_price_record(
        synthetic_raw_price(adj_close="10.25"),
        symbol="NASDAQ:MOCK",
        source="mock-adapter:unit-test",
        currency="USD",
        as_of="2026-01-06",
    )

    assert isinstance(record, PriceRecord)
    assert record.symbol == "NASDAQ:MOCK"
    assert record.date == date(2026, 1, 5)
    assert record.as_of == date(2026, 1, 6)
    assert record.source == "mock-adapter:unit-test"
    assert record.currency == "USD"
    assert record.open == Decimal("10.00")
    assert record.volume == 12345
    assert record.adjusted_close == Decimal("10.25")
    validate_record(record)


def test_adjusted_close_defaults_to_close_when_missing() -> None:
    record = normalize_price_record(
        synthetic_raw_price(),
        symbol="SET:MOCK",
        source="mock-adapter:unit-test",
        currency="THB",
        as_of=date(2026, 1, 6),
    )

    assert record.close == Decimal("10.50")
    assert record.adjusted_close == record.close


def test_adjusted_close_can_be_required() -> None:
    with pytest.raises(NormalizationError, match="adjusted_close is required"):
        normalize_price_record(
            synthetic_raw_price(),
            symbol="HKEX:MOCK",
            source="mock-adapter:unit-test",
            currency="HKD",
            as_of="2026-01-06",
            adjusted_close_policy="require",
        )


def test_normalize_price_records_preserves_order_and_normalizes_dates() -> None:
    records = normalize_price_records(
        [
            synthetic_raw_price(date="2026-01-05", close="10.50"),
            synthetic_raw_price(date="2026-01-06", close="10.75", adjusted_close="10.70"),
        ],
        symbol="NASDAQ:MOCK",
        source="mock-adapter:unit-test",
        currency="USD",
        as_of="2026-01-07T12:34:56Z",
    )

    assert [record.date for record in records] == [date(2026, 1, 5), date(2026, 1, 6)]
    assert [record.close for record in records] == [Decimal("10.50"), Decimal("10.75")]
    assert records[0].adjusted_close == Decimal("10.50")
    assert records[1].adjusted_close == Decimal("10.70")


def test_invalid_currency_fails_schema_validation() -> None:
    with pytest.raises(Exception, match="currency"):
        normalize_price_record(
            synthetic_raw_price(),
            symbol="NASDAQ:MOCK",
            source="mock-adapter:unit-test",
            currency="usd",
            as_of="2026-01-06",
        )


def test_missing_required_raw_field_is_rejected() -> None:
    raw = synthetic_raw_price()
    raw.pop("volume")

    with pytest.raises(NormalizationError, match="volume"):
        normalize_price_record(
            raw,
            symbol="NASDAQ:MOCK",
            source="mock-adapter:unit-test",
            currency="USD",
            as_of="2026-01-06",
        )
