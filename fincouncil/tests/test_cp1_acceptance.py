"""CP1 verification harness — acceptance tests for Phase 1 sprint goal.

CP1 acceptance criteria (from ROADMAP_AND_CHECKPOINTS.md):
1. ``get_price`` for AAPL + .BK + .HK returns data matching reference
   at rounding level.
2. Every record has ``source`` + ``currency``.
3. ``reconcile`` flags injected discrepancies (does not swallow) + writes log.
4. Council run (US ticker) uses data from our layer.

These tests are the **skeleton** — they define the test shapes and pass
against synthetic fixtures.  Live integration tests are marked ``@pytest.mark.live``
and auto-skip when credentials are absent (see conftest.py).

Design reference: PHASE1_DATA_LAYER_SPRINT.md T1.12
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from fincouncil.data.schema import (
    CurrencyCode,
    PriceRecord,
    ReconcileLogRecord,
    ReconcileStatus,
    validate_record,
)
from fincouncil.data.reconcile.engine import (
    DEFAULT_FUNDAMENTALS_THRESHOLD_PCT,
    DEFAULT_PRICE_THRESHOLD_PCT,
    ReconcileEngine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _currency(code: str) -> CurrencyCode:
    return CurrencyCode(code)


# ---------------------------------------------------------------------------
# CP1 Criterion 1: get_price returns data for US / TH / HK
# ---------------------------------------------------------------------------

class TestCP1GetPrice:
    """CP1 criterion 1: get_price works for US, Thai (.BK), HK tickers.

    Skeleton tests verify the schema shape.  Live tests verify actual data.
    """

    def test_price_record_has_required_fields(
        self, synthetic_price_aapl: PriceRecord
    ) -> None:
        """A price record from get_price must carry all OHLCV fields."""
        rec = synthetic_price_aapl
        assert rec.open is not None
        assert rec.high is not None
        assert rec.low is not None
        assert rec.close is not None
        assert rec.volume is not None
        assert rec.adjusted_close is not None

    def test_us_price_has_usd_currency(
        self, synthetic_price_aapl: PriceRecord
    ) -> None:
        """US ticker price records must use USD."""
        assert synthetic_price_aapl.currency == "USD"

    def test_thai_price_has_thb_currency(
        self, synthetic_price_ptt: PriceRecord
    ) -> None:
        """Thai (.BK) ticker price records must use THB."""
        assert synthetic_price_ptt.currency == "THB"

    def test_hk_price_has_hkd_currency(
        self, synthetic_price_00700: PriceRecord
    ) -> None:
        """HK ticker price records must use HKD."""
        assert synthetic_price_00700.currency == "HKD"

    def test_price_symbol_format(self, synthetic_price_aapl: PriceRecord) -> None:
        """Symbol must be in canonical ``{exchange}:{ticker}`` format."""
        assert ":" in synthetic_price_aapl.symbol
        exchange, ticker = synthetic_price_aapl.symbol.split(":", 1)
        assert exchange
        assert ticker

    def test_price_record_validates(self, synthetic_price_aapl: PriceRecord) -> None:
        """Price record must pass schema validation."""
        validate_record(synthetic_price_aapl)

    @pytest.mark.live
    def test_live_get_price_aapl(self) -> None:
        """Live: get_price AAPL returns data matching reference at rounding."""
        pytest.skip("Not yet implemented — depends on T1.4, T1.6")

    @pytest.mark.live
    def test_live_get_price_ptt_bk(self) -> None:
        """Live: get_price PTT.BK returns data with THB currency."""
        pytest.skip("Not yet implemented — depends on T1.4, T1.6")

    @pytest.mark.live
    def test_live_get_price_00700_hk(self) -> None:
        """Live: get_price 00700.HK returns data with HKD currency."""
        pytest.skip("Not yet implemented — depends on T1.4, T1.6")


# ---------------------------------------------------------------------------
# CP1 Criterion 2: Every record has source + currency
# ---------------------------------------------------------------------------

class TestCP1SourceCurrency:
    """CP1 criterion 2: every record carries source and currency tags."""

    def test_price_record_has_source(
        self, synthetic_price_aapl: PriceRecord
    ) -> None:
        """Price record must have a non-empty source."""
        assert synthetic_price_aapl.source

    def test_price_record_has_currency(
        self, synthetic_price_aapl: PriceRecord
    ) -> None:
        """Price record must have a 3-letter currency code."""
        assert len(str(synthetic_price_aapl.currency)) == 3

    def test_fundamentals_record_has_source(
        self, synthetic_fundamentals_aapl: Any
    ) -> None:
        """Fundamentals record must have a non-empty source."""
        assert synthetic_fundamentals_aapl.source

    def test_fundamentals_record_has_currency(
        self, synthetic_fundamentals_aapl: Any
    ) -> None:
        """Fundamentals record must have a 3-letter currency code."""
        assert len(str(synthetic_fundamentals_aapl.currency)) == 3

    @pytest.mark.parametrize(
        "record_fixture",
        ["synthetic_price_aapl", "synthetic_price_ptt", "synthetic_price_00700"],
    )
    def test_all_market_records_have_source_and_currency(
        self, record_fixture: str, request: Any
    ) -> None:
        """Every record across all markets must have source + currency."""
        rec = request.getfixturevalue(record_fixture)
        assert rec.source
        assert rec.currency
        assert len(str(rec.currency)) == 3


# ---------------------------------------------------------------------------
# CP1 Criterion 3: Reconcile flags injected discrepancies
# ---------------------------------------------------------------------------

class TestCP1ReconcileDiscrepancy:
    """CP1 criterion 3: reconcile flags discrepancies, writes log.

    Detailed discrepancy tests live in test_reconcile_discrepancy.py.
    These are the CP1-level acceptance gates.
    """

    def test_injected_discrepancy_is_flagged(self) -> None:
        """Core CP1 gate: a deliberately injected discrepancy MUST be flagged.

        This is the single most important test for the data moat.
        If this fails, the entire reconciliation guarantee is broken.
        """
        engine = ReconcileEngine()
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
        assert record.status == ReconcileStatus.FLAG, (
            "INJECTED DISCREPANCY NOT FLAGGED — reconcile engine is swallowing diffs"
        )
        assert record.diff_pct > DEFAULT_PRICE_THRESHOLD_PCT

    def test_reconcile_result_preserves_source_values(self) -> None:
        """The flagged result must retain all source values for audit."""
        engine = ReconcileEngine()
        values = {"openbb": Decimal("195.50"), "yfinance": Decimal("185.00")}
        record = engine.reconcile(
            symbol="NASDAQ:AAPL",
            field="close",
            as_of=date(2026, 6, 2),
            currency=_currency("USD"),
            values_by_source=values,
            record_kind="price",
        )
        assert dict(record.values) == values

    def test_reconcile_result_has_explanation(self) -> None:
        """Every flagged result must have a human-readable explanation."""
        engine = ReconcileEngine()
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
        assert record.status == ReconcileStatus.FLAG
        assert record.explanation
        assert "DISCREPANCY" in record.explanation

    def test_reconcile_log_validates(self) -> None:
        """The ReconcileLogRecord must pass schema validation."""
        engine = ReconcileEngine()
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
        validate_record(record)

    def test_reconcile_log_shape(self) -> None:
        """ReconcileLogRecord must have all columns for reconcile_log table."""
        engine = ReconcileEngine()
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
        from dataclasses import asdict
        log_dict = asdict(record)
        assert "symbol" in log_dict
        assert "field" in log_dict
        assert "date" in log_dict
        assert "currency" in log_dict
        assert "values" in log_dict
        assert "diff_pct" in log_dict
        assert "threshold_pct" in log_dict
        assert "status" in log_dict
        assert "explanation" in log_dict


# ---------------------------------------------------------------------------
# CP1 Criterion 4: Council uses data from our layer
# ---------------------------------------------------------------------------

class TestCP1CouncilDataLayer:
    """CP1 criterion 4: council run uses data from our layer (not fork defaults).

    This is the integration test shape.  It depends on T1.11 (swap-in).
    The skeleton verifies the contract; live tests run after T1.11.
    """

    @pytest.mark.live
    def test_live_council_uses_our_data_layer(self) -> None:
        """Live: council run on US ticker pulls from our data layer."""
        pytest.skip("Not yet implemented — depends on T1.11 swap-in")

    def test_swap_in_adapter_interface_exists(self) -> None:
        """The adapter interface our swap-in will implement must exist."""
        from fincouncil.data.adapters.base import BaseAdapter
        assert hasattr(BaseAdapter, "get_price")
        assert hasattr(BaseAdapter, "get_fundamentals")
        assert hasattr(BaseAdapter, "is_available")

    def test_reconcile_engine_exists(self) -> None:
        """The reconcile engine must be importable and functional."""
        from fincouncil.data.reconcile.engine import ReconcileEngine
        engine = ReconcileEngine()
        assert callable(engine.reconcile)


# ---------------------------------------------------------------------------
# CP1 Credential gate — no fabricated output
# ---------------------------------------------------------------------------

class TestCP1CredentialGate:
    """Enforce CP0 credential blocker: no live tests without credentials."""

    def test_no_hardcoded_financial_values_in_engine(self) -> None:
        """Production reconcile engine must not contain hardcoded financial values.

        This is a smoke test — it checks the reconcile engine module
        for suspicious numeric literals that look like stock prices.
        """
        import inspect
        import ast

        source = inspect.getsource(ReconcileEngine)
        tree = ast.parse(source)

        suspicious = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                val = abs(node.value)
                # Skip common arithmetic constants
                if val in (0, 1, 2, 100):
                    continue
                if 100 <= val <= 99999:
                    suspicious.append((node.lineno, node.value))

        assert len(suspicious) == 0, (
            f"Possible hardcoded financial values found at lines: {suspicious}"
        )
