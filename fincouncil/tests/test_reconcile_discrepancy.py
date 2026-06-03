"""Reconcile discrepancy test shape — the core moat test.

These tests verify that the ``ReconcileEngine`` correctly:
1. Passes when values agree within threshold.
2. Flags when values exceed the threshold.
3. Flags **injected discrepancies** — never swallows them.
4. Handles edge cases (zero values, single source, negative values).
5. Uses the correct threshold for price vs fundamentals.

This is the test shape referenced by T1.8 and CP1 acceptance criterion 3:
"reconcile flag discrepancy ที่ฉีดเข้าไป (ไม่กลืน) + เขียน log"

All data here is synthetic test fixtures — no live provider calls.
"""

from __future__ import annotations

from datetime import date

import pytest

from fincouncil.data.reconcile.engine import ReconcileEngine
from fincouncil.data.schema import (
    RECONCILE_THRESHOLD_PRICE_PCT,
    RECONCILE_THRESHOLD_FUNDAMENTALS_PCT,
    ReconcileResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> ReconcileEngine:
    return ReconcileEngine()


# ---------------------------------------------------------------------------
# Lane 1: Matching values — should NOT flag
# ---------------------------------------------------------------------------

class TestMatchingValues:
    """When two sources agree, reconcile should pass (not flag)."""

    def test_identical_price_values_not_flagged(self, engine: ReconcileEngine) -> None:
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50, "yfinance": 195.50},
            record_type="price",
        )
        assert not result.flagged
        assert result.diff_pct == 0.0

    def test_near_identical_price_within_threshold(self, engine: ReconcileEngine) -> None:
        """Values differing by less than 0.5% should NOT be flagged."""
        # 195.50 vs 195.48 → diff ≈ 0.0102%
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50, "yfinance": 195.48},
            record_type="price",
        )
        assert not result.flagged
        assert result.diff_pct < RECONCILE_THRESHOLD_PRICE_PCT

    def test_exactly_at_threshold_not_flagged(self, engine: ReconcileEngine) -> None:
        """Diff exactly at threshold (0.5%) should NOT be flagged (uses >)."""
        # mean=200, diff=1.0 → 0.5% exactly
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 200.50, "yfinance": 199.50},
            record_type="price",
        )
        # diff_pct = 1.0 / 200.0 * 100 = 0.5% exactly → NOT flagged (uses >)
        assert not result.flagged


# ---------------------------------------------------------------------------
# Lane 2: Discrepancy detection — MUST flag
# ---------------------------------------------------------------------------

class TestDiscrepancyDetection:
    """When values differ beyond threshold, reconcile MUST flag."""

    def test_injected_price_discrepancy_flagged(self, engine: ReconcileEngine) -> None:
        """CP1 core test: an injected discrepancy (e.g. 5%) MUST be flagged.

        This is the test that proves reconcile does not swallow differences.
        """
        # openbb=195.50, yfinance=185.00 → diff ≈ 5.5% >> 0.5%
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50, "yfinance": 185.00},
            record_type="price",
        )
        assert result.flagged is True
        assert result.diff_pct > RECONCILE_THRESHOLD_PRICE_PCT
        assert "DISCREPANCY" in result.explanation

    def test_large_injected_discrepancy_flagged(self, engine: ReconcileEngine) -> None:
        """A deliberately large discrepancy (50%) must absolutely be flagged."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.00, "yfinance": 130.00},
            record_type="price",
        )
        assert result.flagged is True
        assert result.diff_pct >= 40.0  # ~40% (195 vs 130 = 40.0% exactly)

    def test_fundamentals_discrepancy_flagged(self, engine: ReconcileEngine) -> None:
        """Fundamentals use 1% threshold — a 5% diff must be flagged."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="revenue",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 391_000, "yfinance": 370_000},
            record_type="fundamentals",
        )
        assert result.flagged is True
        assert result.diff_pct > RECONCILE_THRESHOLD_FUNDAMENTALS_PCT

    def test_price_discrepancy_would_pass_as_fundamentals(self, engine: ReconcileEngine) -> None:
        """A 0.6% diff flags for price (0.5%) but not fundamentals (1%)."""
        result_price = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 100.0, "yfinance": 100.6},
            record_type="price",
        )
        result_fund = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="revenue",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 100.0, "yfinance": 100.6},
            record_type="fundamentals",
        )
        assert result_price.flagged is True   # 0.6% > 0.5%
        assert result_fund.flagged is False   # 0.6% < 1.0%


# ---------------------------------------------------------------------------
# Lane 3: Edge cases
# ---------------------------------------------------------------------------

class TestReconcileEdgeCases:
    """Edge cases that must not crash or produce wrong results."""

    def test_single_source_no_flag(self, engine: ReconcileEngine) -> None:
        """Only one source → cannot reconcile, should not flag."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50},
            record_type="price",
        )
        assert not result.flagged
        assert result.diff_pct is None
        assert "Only 1 source" in result.explanation

    def test_three_sources_flagged_when_one_outlier(self, engine: ReconcileEngine) -> None:
        """With 3 sources, if one is an outlier, the result is still flagged."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={
                "openbb": 195.50,
                "yfinance": 195.48,
                "alpha_vantage": 170.00,  # outlier
            },
            record_type="price",
        )
        assert result.flagged is True

    def test_negative_values(self, engine: ReconcileEngine) -> None:
        """Negative values (e.g. EPS loss) should reconcile correctly."""
        result = engine.reconcile(
            symbol="NYSE:LOSS",
            field="eps",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": -1.50, "yfinance": -1.50},
            record_type="fundamentals",
        )
        assert not result.flagged
        assert result.diff_pct == 0.0

    def test_zero_mean_handles_gracefully(self, engine: ReconcileEngine) -> None:
        """When mean is zero, engine should not raise ZeroDivisionError."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 0.0, "yfinance": 0.0},
            record_type="price",
        )
        assert not result.flagged

    def test_result_contains_all_source_values(self, engine: ReconcileEngine) -> None:
        """The result must preserve every source value for audit trail."""
        values = {"openbb": 195.50, "yfinance": 185.00}
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source=values,
            record_type="price",
        )
        assert result.values == values
        assert "openbb" in result.values
        assert "yfinance" in result.values

    def test_result_is_frozen_dataclass(self, engine: ReconcileEngine) -> None:
        """ReconcileResult must be immutable (frozen dataclass)."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50, "yfinance": 195.48},
            record_type="price",
        )
        with pytest.raises(AttributeError):
            result.flagged = True  # type: ignore[misc]

    def test_custom_threshold_override(self, engine: ReconcileEngine) -> None:
        """Tests can override thresholds for specific scenarios."""
        # 1% diff → would flag at default 0.5%, but we set 2% threshold
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 100.00, "yfinance": 101.00},
            record_type="price",
            price_threshold_pct=2.0,
        )
        assert not result.flagged  # 1% < 2% override


# ---------------------------------------------------------------------------
# Lane 4: Reconcile log shape (for store layer integration)
# ---------------------------------------------------------------------------

class TestReconcileLogShape:
    """Verify that reconcile results can be persisted to the reconcile_log.

    These tests verify the *shape* of the output, not the storage
    implementation (which comes in T1.3/T1.7).
    """

    def test_result_has_all_required_fields(self, engine: ReconcileEngine) -> None:
        """A ReconcileResult must carry every field needed for logging."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50, "yfinance": 185.00},
            record_type="price",
        )
        # Required fields for reconcile_log table
        assert hasattr(result, "symbol")
        assert hasattr(result, "field")
        assert hasattr(result, "as_of")
        assert hasattr(result, "currency")
        assert hasattr(result, "values")
        assert hasattr(result, "diff_pct")
        assert hasattr(result, "flagged")
        assert hasattr(result, "explanation")

    def test_result_is_serializable(self, engine: ReconcileEngine) -> None:
        """ReconcileResult should be convertible to a dict for storage."""
        result = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency="USD",
            values_by_source={"openbb": 195.50, "yfinance": 185.00},
            record_type="price",
        )
        # dataclasses.asdict should work on frozen dataclasses
        from dataclasses import asdict
        d = asdict(result)
        assert isinstance(d, dict)
        assert d["symbol"] == "NASDAQ:AAPL"
        assert d["flagged"] is True
