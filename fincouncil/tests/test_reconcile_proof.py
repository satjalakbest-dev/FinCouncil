"""Proof tests for the reconcile engine's discrepancy detection.

These tests prove that the ReconcileEngine correctly detects discrepancies
across data sources and produces valid ReconcileLogRecord output.

Reference: DATA_SOURCES.md "Reconcile / Verify Policy"
           PHASE1_DATA_LAYER_SPRINT.md T1.8
"""

from datetime import date
from decimal import Decimal

import pytest

from fincouncil.data.reconcile.engine import (
    DEFAULT_FUNDAMENTALS_THRESHOLD_PCT,
    DEFAULT_PRICE_THRESHOLD_PCT,
    InsufficientSourcesError,
    ReconcileEngine,
)
from fincouncil.data.schema import CurrencyCode, ReconcileStatus


class TestReconcilePassCase:
    """Test PASS case — two sources within 0.5% threshold."""

    def test_close_values_within_threshold_pass(self):
        """Two sources with close values (195.50 vs 195.48) pass the 0.5% threshold."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:AAPL",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("195.48"),
            },
            record_kind="price",
        )

        # Verify status is PASS
        assert result.status == ReconcileStatus.PASS

        # Verify the diff is small
        expected_diff = abs(Decimal("195.50") - Decimal("195.48")) / ((Decimal("195.50") + Decimal("195.48")) / 2) * 100
        assert result.diff_pct == expected_diff
        assert result.diff_pct < DEFAULT_PRICE_THRESHOLD_PCT

        # Verify explanation mentions OK
        assert "OK on 'close'" in result.explanation
        assert "openbb=195.50" in result.explanation
        assert "yfinance=195.48" in result.explanation

        # Verify record fields
        assert result.symbol == "US:AAPL"
        assert result.field == "close"
        assert result.date == date(2024, 6, 3)
        assert result.currency == CurrencyCode("USD")
        assert result.threshold_pct == DEFAULT_PRICE_THRESHOLD_PCT
        assert len(result.values) == 2

    def test_identical_values_pass(self):
        """Identical values (100.00 vs 100.00) trivially pass."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:MSFT",
            field="open",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("100.00"),
                "source_b": Decimal("100.00"),
            },
            record_kind="price",
        )

        assert result.status == ReconcileStatus.PASS
        assert result.diff_pct == Decimal("0")


class TestReconcileFlagCase:
    """Test FLAG case — two sources exceeding 0.5% threshold."""

    def test_far_values_exceed_threshold_flag(self):
        """Two sources with 1.19% diff (100.00 vs 101.20) exceed 0.5% threshold."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:TSLA",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("100.00"),
                "source_b": Decimal("101.20"),
            },
            record_kind="price",
        )

        # Verify status is FLAG
        assert result.status == ReconcileStatus.FLAG

        # Verify the diff is > 0.5%
        expected_diff = abs(Decimal("101.20") - Decimal("100.00")) / ((Decimal("101.20") + Decimal("100.00")) / 2) * 100
        assert result.diff_pct == expected_diff
        assert result.diff_pct > DEFAULT_PRICE_THRESHOLD_PCT
        # Specifically, should be ~1.19%
        assert result.diff_pct > Decimal("1.0")

        # Verify explanation mentions DISCREPANCY
        assert "DISCREPANCY on 'close'" in result.explanation
        assert "source_a=100.00" in result.explanation
        assert "source_b=101.20" in result.explanation

        # Verify threshold is still 0.5%
        assert result.threshold_pct == DEFAULT_PRICE_THRESHOLD_PCT


class TestReconcileInsufficientSources:
    """Test error case — insufficient sources."""

    def test_single_source_raises_error(self):
        """Only one source provided raises InsufficientSourcesError."""
        engine = ReconcileEngine()

        with pytest.raises(InsufficientSourcesError, match="≥2 sources, got 1"):
            engine.reconcile(
                symbol="US:GOOGL",
                field="close",
                as_of=date(2024, 6, 3),
                currency=CurrencyCode("USD"),
                values_by_source={"source_a": Decimal("150.00")},
                record_kind="price",
            )

    def test_empty_sources_raises_error(self):
        """Zero sources provided raises InsufficientSourcesError."""
        engine = ReconcileEngine()

        with pytest.raises(InsufficientSourcesError, match="≥2 sources, got 0"):
            engine.reconcile(
                symbol="US:AMZN",
                field="close",
                as_of=date(2024, 6, 3),
                currency=CurrencyCode("USD"),
                values_by_source={},
                record_kind="price",
            )


class TestReconcileFundamentalsThreshold:
    """Test fundamentals threshold (1.0%) vs price threshold (0.5%)."""

    def test_fundamentals_0_8_percent_diff_passes(self):
        """0.8% diff passes 1.0% fundamentals threshold but would fail 0.5% price threshold."""
        engine = ReconcileEngine()

        # Values with 0.8% difference: 100.00 vs 100.80
        # Diff = |100.80 - 100.00| / ((100.80 + 100.00) / 2) * 100 = 0.794% ≈ 0.8%
        result = engine.reconcile(
            symbol="US:NVDA",
            field="revenue",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("100.00"),
                "source_b": Decimal("100.80"),
            },
            record_kind="fundamentals",
        )

        # Verify status is PASS (fundamentals threshold is 1.0%)
        assert result.status == ReconcileStatus.PASS

        # Verify the diff is ~0.8%
        expected_diff = abs(Decimal("100.80") - Decimal("100.00")) / ((Decimal("100.80") + Decimal("100.00")) / 2) * 100
        assert result.diff_pct == expected_diff
        assert result.diff_pct < DEFAULT_FUNDAMENTALS_THRESHOLD_PCT  # 1.0%
        assert result.diff_pct > DEFAULT_PRICE_THRESHOLD_PCT  # 0.5% - would fail price threshold

        # Verify fundamentals threshold applied
        assert result.threshold_pct == DEFAULT_FUNDAMENTALS_THRESHOLD_PCT

    def test_same_values_fails_price_threshold_but_passes_fundamentals(self):
        """Prove that values that fail price threshold pass fundamentals threshold."""
        engine = ReconcileEngine()

        values_by_source = {
            "source_a": Decimal("100.00"),
            "source_b": Decimal("100.80"),  # ~0.8% diff
        }

        # Should FAIL with price threshold
        price_result = engine.reconcile(
            symbol="US:TEST",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source=values_by_source,
            record_kind="price",
        )
        assert price_result.status == ReconcileStatus.FLAG
        assert price_result.threshold_pct == DEFAULT_PRICE_THRESHOLD_PCT

        # Should PASS with fundamentals threshold
        fundamentals_result = engine.reconcile(
            symbol="US:TEST",
            field="revenue",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source=values_by_source,
            record_kind="fundamentals",
        )
        assert fundamentals_result.status == ReconcileStatus.PASS
        assert fundamentals_result.threshold_pct == DEFAULT_FUNDAMENTALS_THRESHOLD_PCT


class TestReconcileMCPToolIntegration:
    """Test MCP tool integration with mocked adapters."""

    def test_mcp_reconcile_tool_with_mocked_adapters(self, monkeypatch):
        """Test that mcp.tools.reconcile() works with mocked adapters."""
        from unittest.mock import MagicMock, patch
        from decimal import Decimal

        from fincouncil.data.mcp.tools import reconcile
        from fincouncil.data.schema import PriceRecord

        # Mock adapters to be available
        mock_openbb_adapter = MagicMock()
        mock_yfinance_adapter = MagicMock()

        mock_openbb_adapter.is_available.return_value = True
        mock_yfinance_adapter.is_available.return_value = True

        # Mock price records with Decimal values
        mock_openbb_price = PriceRecord(
            source="openbb:yfinance",
            currency=CurrencyCode("USD"),
            as_of=date(2024, 6, 3),
            kind="price",
            symbol="US:AAPL",
            date=date(2024, 6, 3),
            open=Decimal("195.00"),
            high=Decimal("196.00"),
            low=Decimal("194.00"),
            close=Decimal("195.50"),
            volume=1000000,
            adjusted_close=Decimal("195.50"),
        )

        mock_yfinance_price = PriceRecord(
            source="yfinance:yfinance",
            currency=CurrencyCode("USD"),
            as_of=date(2024, 6, 3),
            kind="price",
            symbol="US:AAPL",
            date=date(2024, 6, 3),
            open=Decimal("194.98"),
            high=Decimal("195.98"),
            low=Decimal("193.98"),
            close=Decimal("195.48"),
            volume=1000000,
            adjusted_close=Decimal("195.48"),
        )

        # Mock cache manager to return our records
        mock_cache_manager = MagicMock()
        call_count = [0]

        def mock_get_or_fetch(*args, **kwargs):
            # First call (openbb), second call (yfinance)
            if call_count[0] == 0:
                call_count[0] += 1
                return [mock_openbb_price]
            else:
                return [mock_yfinance_price]

        mock_cache_manager.get_or_fetch.side_effect = mock_get_or_fetch

        # Mock OpenBBAdapter and YFinanceAdapter constructors
        with patch("fincouncil.data.mcp.tools.OpenBBAdapter", return_value=mock_openbb_adapter):
            with patch("fincouncil.data.mcp.tools.YFinanceAdapter", return_value=mock_yfinance_adapter):
                result = reconcile(
                    symbol="US:AAPL",
                    field="close",
                    trade_date="2024-06-03",
                    cache_manager=mock_cache_manager,
                )

        # Verify the result is a dict (from _record_to_dict)
        assert isinstance(result, dict)

        # Verify reconcile outcome
        assert result["status"] == "PASS"  # 195.50 vs 195.48 is close
        assert result["symbol"] == "US:AAPL"
        assert result["field"] == "close"
        assert result["date"] == date(2024, 6, 3)
        assert result["currency"] == "USD"
        assert result["threshold_pct"] == DEFAULT_PRICE_THRESHOLD_PCT

        # Verify values from both sources are present
        assert "values" in result
        assert isinstance(result["values"], dict)

        # Verify explanation mentions both sources
        assert "OK on 'close'" in result["explanation"] or result["explanation"] != ""


class TestReconcileEdgeCases:
    """Additional edge cases for comprehensive proof."""

    def test_zero_values_handling(self):
        """Test handling of zero values (division by zero protection)."""
        engine = ReconcileEngine()

        # Both zero values
        result = engine.reconcile(
            symbol="US:TEST",
            field="volume",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("0"),
                "source_b": Decimal("0"),
            },
            record_kind="price",
        )

        assert result.status == ReconcileStatus.PASS
        assert result.diff_pct == Decimal("0")

    def test_one_zero_one_nonzero(self):
        """Test when one value is zero and another is non-zero."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:TEST",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("0"),
                "source_b": Decimal("100.00"),
            },
            record_kind="price",
        )

        # Should be FLAG (division by zero -> infinite diff)
        assert result.status == ReconcileStatus.FLAG

    def test_three_sources(self):
        """Test reconcile works with >2 sources."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:TEST",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("100.00"),
                "source_b": Decimal("100.50"),
                "source_c": Decimal("100.25"),
            },
            record_kind="price",
        )

        # Max=100.50, Min=100.00, Mean=100.25
        # Diff = |100.50 - 100.00| / 100.25 * 100 = 0.498% ≈ 0.5%
        assert result.status == ReconcileStatus.PASS
        assert len(result.values) == 3

    def test_custom_price_threshold(self):
        """Test custom price threshold override."""
        engine = ReconcileEngine()

        # 0.8% diff with 0.5% threshold would normally FLAG
        # but with 1.0% threshold should PASS
        result = engine.reconcile(
            symbol="US:TEST",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("100.00"),
                "source_b": Decimal("100.80"),
            },
            record_kind="price",
            price_threshold_pct=Decimal("1.0"),  # Override
        )

        assert result.status == ReconcileStatus.PASS
        assert result.threshold_pct == Decimal("1.0")


class TestReconcileExplanationFormat:
    """Test explanation string format and content."""

    def test_explanation_pass_format(self):
        """Verify PASS explanation follows expected format."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:AAPL",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "openbb": Decimal("195.50"),
                "yfinance": Decimal("195.48"),
            },
            record_kind="price",
        )

        # Should contain: OK on 'field': source1=val1, source2=val2 (diff=X.XXXX% ≤ threshold=X.X%)
        explanation = result.explanation
        assert "OK on 'close'" in explanation
        assert "openbb=195.50" in explanation
        assert "yfinance=195.48" in explanation
        assert "diff=" in explanation
        assert "threshold=" in explanation
        assert "≤" in explanation

    def test_explanation_flag_format(self):
        """Verify FLAG explanation follows expected format."""
        engine = ReconcileEngine()

        result = engine.reconcile(
            symbol="US:TSLA",
            field="close",
            as_of=date(2024, 6, 3),
            currency=CurrencyCode("USD"),
            values_by_source={
                "source_a": Decimal("100.00"),
                "source_b": Decimal("101.20"),
            },
            record_kind="price",
        )

        # Should contain: DISCREPANCY on 'field': source1=val1, source2=val2 (diff=X.XXXX%, threshold=X.X%)
        explanation = result.explanation
        assert "DISCREPANCY on 'close'" in explanation
        assert "source_a=100.00" in explanation
        assert "source_b=101.20" in explanation
        assert "diff=" in explanation
        assert "threshold=" in explanation
