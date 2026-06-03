"""Reconcile discrepancy test shape — the core moat test.

These tests verify that the ``ReconcileEngine`` correctly:
1. Passes when values agree within threshold.
2. Flags when values exceed the threshold.
3. Flags **injected discrepancies** — never swallows them.
4. Handles edge cases (zero values, single source, negative values).
5. Uses the correct threshold for price vs fundamentals.
6. Produces canonical ``ReconcileLogRecord`` objects.

This is the test shape referenced by T1.8 and CP1 acceptance criterion 3:
"reconcile flag discrepancy ที่ฉีดเข้าไป (ไม่กลืน) + เขียน log"

All data here is synthetic test fixtures — no live provider calls.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from fincouncil.data.reconcile.engine import (
    DEFAULT_FUNDAMENTALS_THRESHOLD_PCT,
    DEFAULT_PRICE_THRESHOLD_PCT,
    InsufficientSourcesError,
    ReconcileEngine,
)
from fincouncil.data.schema import (
    CurrencyCode,
    ReconcileLogRecord,
    ReconcileStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _currency(code: str) -> CurrencyCode:
    return CurrencyCode(code)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> ReconcileEngine:
    return ReconcileEngine()


# ---------------------------------------------------------------------------
# Lane 1: Matching values — should PASS
# ---------------------------------------------------------------------------

class TestMatchingValues:
    """When two sources agree, reconcile should pass (not flag)."""

    def test_identical_price_values_pass(self, engine: ReconcileEngine) -> None:
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("195.50"),
            },
            record_kind="price",
        )
        assert record.status == ReconcileStatus.PASS
        assert record.diff_pct == Decimal("0")

    def test_near_identical_price_within_threshold(self, engine: ReconcileEngine) -> None:
        """Values differing by less than 0.5% should PASS."""
        # 195.50 vs 195.48 → diff ≈ 0.0102%
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("195.48"),
            },
            record_kind="price",
        )
        assert record.status == ReconcileStatus.PASS
        assert record.diff_pct < DEFAULT_PRICE_THRESHOLD_PCT

    def test_exactly_at_threshold_pass(self, engine: ReconcileEngine) -> None:
        """Diff exactly at threshold (0.5%) should PASS (uses >)."""
        # mean=200, diff=1.0 → 0.5% exactly → PASS (uses > not >=)
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("200.50"),
                "yfinance": Decimal("199.50"),
            },
            record_kind="price",
        )
        # diff_pct = 1.0 / 200.0 * 100 = 0.5% exactly → PASS (uses >)
        assert record.status == ReconcileStatus.PASS


# ---------------------------------------------------------------------------
# Lane 2: Discrepancy detection — MUST FLAG
# ---------------------------------------------------------------------------

class TestDiscrepancyDetection:
    """When values differ beyond threshold, reconcile MUST flag."""

    def test_injected_price_discrepancy_flagged(self, engine: ReconcileEngine) -> None:
        """CP1 core test: an injected discrepancy (e.g. 5%) MUST be flagged.

        This is the test that proves reconcile does not swallow differences.
        """
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("185.00"),  # 5.4% discrepancy — injected
            },
            record_kind="price",
        )
        assert record.status == ReconcileStatus.FLAG
        assert record.diff_pct > DEFAULT_PRICE_THRESHOLD_PCT
        assert "DISCREPANCY" in record.explanation

    def test_large_injected_discrepancy_flagged(self, engine: ReconcileEngine) -> None:
        """A deliberately large discrepancy (40%) must absolutely be flagged."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.00"),
                "yfinance": Decimal("130.00"),
            },
            record_kind="price",
        )
        assert record.status == ReconcileStatus.FLAG
        assert record.diff_pct >= Decimal("40")  # ~40% (195 vs 130)

    def test_fundamentals_discrepancy_flagged(self, engine: ReconcileEngine) -> None:
        """Fundamentals use 1% threshold — a ~5.4% diff must be flagged."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="revenue",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("391000"),
                "yfinance": Decimal("370000"),
            },
            record_kind="fundamentals",
        )
        assert record.status == ReconcileStatus.FLAG
        assert record.diff_pct > DEFAULT_FUNDAMENTALS_THRESHOLD_PCT

    def test_price_discrepancy_would_pass_as_fundamentals(self, engine: ReconcileEngine) -> None:
        """A 0.6% diff flags for price (0.5%) but not fundamentals (1%)."""
        record_price = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("100.00"),
                "yfinance": Decimal("100.60"),
            },
            record_kind="price",
        )
        record_fund = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="revenue",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("100.00"),
                "yfinance": Decimal("100.60"),
            },
            record_kind="fundamentals",
        )
        assert record_price.status == ReconcileStatus.FLAG   # 0.6% > 0.5%
        assert record_fund.status == ReconcileStatus.PASS    # 0.6% < 1.0%


# ---------------------------------------------------------------------------
# Lane 3: Edge cases
# ---------------------------------------------------------------------------

class TestReconcileEdgeCases:
    """Edge cases that must not crash or produce wrong results."""

    def test_single_source_raises(self, engine: ReconcileEngine) -> None:
        """Only one source → must raise InsufficientSourcesError."""
        with pytest.raises(InsufficientSourcesError):
            engine.reconcile(
                symbol="NASDAQ:AAPL",
                field="close",
                as_of=date(2026, 6, 2),
                currency=_currency("USD"),
                values_by_source={"openbb": Decimal("195.50")},
                record_kind="price",
            )

    def test_three_sources_flagged_when_one_outlier(self, engine: ReconcileEngine) -> None:
        """With 3 sources, if one is an outlier, the result is still flagged."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("195.48"),
                "alpha_vantage": Decimal("170.00"),  # outlier
            },
            record_kind="price",
        )
        assert record.status == ReconcileStatus.FLAG

    def test_negative_values(self, engine: ReconcileEngine) -> None:
        """Negative values (e.g. EPS loss) should reconcile correctly."""
        record = engine.reconcile(
            symbol="NYSE:LOSS",
            field="eps",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("-1.50"),
                "yfinance": Decimal("-1.50"),
            },
            record_kind="fundamentals",
        )
        assert record.status == ReconcileStatus.PASS
        assert record.diff_pct == Decimal("0")

    def test_zero_mean_handles_gracefully(self, engine: ReconcileEngine) -> None:
        """When mean is zero, engine should not raise ZeroDivisionError."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("0"),
                "yfinance": Decimal("0"),
            },
            record_kind="price",
        )
        assert record.status == ReconcileStatus.PASS

    def test_result_contains_all_source_values(self, engine: ReconcileEngine) -> None:
        """The result must preserve every source value for audit trail."""
        values = {
            "openbb": Decimal("195.50"),
            "yfinance": Decimal("185.00"),
        }
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source=values,
            record_kind="price",
        )
        assert dict(record.values) == values
        assert "openbb" in record.values
        assert "yfinance" in record.values

    def test_result_is_frozen_dataclass(self, engine: ReconcileEngine) -> None:
        """ReconcileLogRecord must be immutable (frozen dataclass)."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("195.48"),
            },
            record_kind="price",
        )
        with pytest.raises(AttributeError):
            record.status = ReconcileStatus.FLAG  # type: ignore[misc]

    def test_custom_threshold_override(self, engine: ReconcileEngine) -> None:
        """Tests can override thresholds for specific scenarios."""
        # 1% diff → would flag at default 0.5%, but we set 2% threshold
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("100.00"),
                "yfinance": Decimal("101.00"),
            },
            record_kind="price",
            price_threshold_pct=Decimal("2.0"),
        )
        assert record.status == ReconcileStatus.PASS  # 1% < 2% override


# ---------------------------------------------------------------------------
# Lane 4: Reconcile log shape (for store layer integration)
# ---------------------------------------------------------------------------

class TestReconcileLogShape:
    """Verify that reconcile results are valid ReconcileLogRecord objects.

    These tests verify the output shape is compatible with DuckDB storage.
    """

    def test_result_is_reconcile_log_record(self, engine: ReconcileEngine) -> None:
        """reconcile() must return a ReconcileLogRecord."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("185.00"),
            },
            record_kind="price",
        )
        assert isinstance(record, ReconcileLogRecord)

    def test_result_has_all_required_fields(self, engine: ReconcileEngine) -> None:
        """A ReconcileLogRecord must carry every field needed for logging."""
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("185.00"),
            },
            record_kind="price",
        )
        # Required fields for reconcile_log table
        assert record.symbol == "NASDAQ:AAPL"
        assert record.field == "close"
        assert record.date == date(2026, 6, 2)
        assert record.currency == _currency("USD")
        assert len(record.values) == 2
        assert record.diff_pct is not None
        assert record.threshold_pct is not None
        assert isinstance(record.status, ReconcileStatus)
        assert record.explanation

    def test_result_validates_against_schema(self, engine: ReconcileEngine) -> None:
        """The ReconcileLogRecord must pass schema validation."""
        from fincouncil.data.schema import validate_record

        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("185.00"),
            },
            record_kind="price",
        )
        # Must not raise
        validate_record(record)

    def test_result_is_serializable(self, engine: ReconcileEngine) -> None:
        """ReconcileLogRecord should be convertible to a dict for storage."""
        from dataclasses import asdict

        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("185.00"),
            },
            record_kind="price",
        )
        d = asdict(record)
        assert isinstance(d, dict)
        assert d["symbol"] == "NASDAQ:AAPL"
        assert d["status"] == ReconcileStatus.FLAG
