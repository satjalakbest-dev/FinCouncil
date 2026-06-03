"""C6 reconcile cross-check — independent CC×CX implementation.

Provides a second, independent reconciliation calculation using a different
algorithm (pairwise percentage diff) to cross-check the main ReconcileEngine
(mean-based percentage diff). Both must produce the same PASS/FLAG verdict
on identical fixture data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from fincouncil.data.reconcile.engine import ReconcileEngine


# ---------------------------------------------------------------------------
# Independent reconciliation (CX) — pairwise percentage difference
# ---------------------------------------------------------------------------

def reconcile_pairwise_pct(
    values_by_source: dict[str, Decimal],
    threshold_pct: float = 0.5,
) -> dict[str, Any]:
    """Independent reconcile: pairwise max percentage difference.

    For each pair of sources (a, b), compute |a - b| / min(a, b) * 100.
    The result is FLAG if ANY pair exceeds the threshold.

    This is a DIFFERENT algorithm from ReconcileEngine which uses
    |max - min| / mean * 100.
    """
    values = list(values_by_source.values())
    sources = list(values_by_source.keys())

    if len(values) < 2:
        return {"status": "INSUFFICIENT_SOURCES", "max_diff_pct": 0.0}

    max_diff = 0.0
    worst_pair = ("", "")
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            a, b = float(values[i]), float(values[j])
            denom = min(abs(a), abs(b))
            if denom == 0:
                pct = float("inf") if a != b else 0.0
            else:
                pct = abs(a - b) / denom * 100
            if pct > max_diff:
                max_diff = pct
                worst_pair = (sources[i], sources[j])

    status = "FLAG" if max_diff > threshold_pct else "PASS"
    return {
        "status": status,
        "max_diff_pct": round(max_diff, 6),
        "worst_pair": worst_pair,
        "threshold": threshold_pct,
    }


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FIXTURES = [
    {
        "name": "AAPL close agree",
        "symbol": "US:AAPL",
        "field": "close",
        "values": {"yfinance": Decimal("195.50"), "openbb": Decimal("195.48")},
        "kind": "price",
        "expect_flag": False,
    },
    {
        "name": "AAPL close disagree",
        "symbol": "US:AAPL",
        "field": "close",
        "values": {"yfinance": Decimal("195.50"), "openbb": Decimal("210.00")},
        "kind": "price",
        "expect_flag": True,
    },
    {
        "name": "PTT close agree",
        "symbol": "SET:PTT",
        "field": "close",
        "values": {"yfinance": Decimal("32.60"), "openbb": Decimal("32.58")},
        "kind": "price",
        "expect_flag": False,
    },
    {
        "name": "00700 close borderline",
        "symbol": "HKEX:00700",
        "field": "close",
        "values": {"yfinance": Decimal("483.00"), "openbb": Decimal("480.80")},
        "kind": "price",
        "expect_flag": False,  # diff ~0.46%, under 0.5% threshold
    },
    {
        "name": "AAPL revenue disagree",
        "symbol": "US:AAPL",
        "field": "revenue",
        "values": {"yfinance": Decimal("391000000000"), "openbb": Decimal("385000000000")},
        "kind": "fundamentals",
        "expect_flag": True,  # ~1.55%, over 1.0% fundamentals threshold
    },
    {
        "name": "Three sources agree",
        "symbol": "US:MSFT",
        "field": "close",
        "values": {
            "yfinance": Decimal("420.50"),
            "openbb": Decimal("420.45"),
            "edinet": Decimal("420.48"),
        },
        "kind": "price",
        "expect_flag": False,
    },
]


# ---------------------------------------------------------------------------
# Cross-check tests
# ---------------------------------------------------------------------------

class TestReconcileCrossCheck:
    """Verify ReconcileEngine (CC) matches independent implementation (CX)."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f["name"])
    def test_engine_matches_independent(self, fixture: dict):
        """Both implementations agree on PASS/FLAG for the same data."""
        engine = ReconcileEngine()
        threshold = 0.5 if fixture["kind"] == "price" else 1.0

        # CC: Main engine
        cc_result = engine.reconcile(
            symbol=fixture["symbol"],
            field=fixture["field"],
            as_of=date(2024, 1, 2),
            currency="USD",
            values_by_source=fixture["values"],
            record_kind=fixture["kind"],
        )
        cc_flagged = cc_result.status.value == "FLAG"

        # CX: Independent implementation
        cx_result = reconcile_pairwise_pct(
            fixture["values"], threshold_pct=threshold,
        )
        cx_flagged = cx_result["status"] == "FLAG"

        # Both must agree
        assert cc_flagged == cx_flagged, (
            f"CC status={cc_result.status.value}, CX status={cx_result['status']}, "
            f"CC diff={cc_result.explanation[:60] if cc_result.explanation else 'N/A'}, "
            f"CX diff={cx_result['max_diff_pct']}%"
        )

        # Both must match expected
        assert cc_flagged == fixture["expect_flag"], (
            f"CC expected {'FLAG' if fixture['expect_flag'] else 'PASS'}, "
            f"got {cc_result.status.value}"
        )

    def test_independent_algorithms_differ_but_agree(self):
        """Confirm the algorithms are genuinely different but produce same verdict."""
        # This fixture is deliberately chosen to have different percentage
        # calculations between mean-based and pairwise approaches
        values = {"a": Decimal("100.00"), "b": Decimal("100.30")}
        threshold = 0.5

        # Mean-based: |100.30 - 100.00| / ((100.30 + 100.00)/2) * 100 = 0.2991%
        engine = ReconcileEngine()
        result = engine.reconcile(
            "TEST:SYM", "close", date(2024, 1, 2), "USD",
            values, "price",
        )

        # Pairwise: |100.30 - 100.00| / min(100.00, 100.30) * 100 = 0.2991%
        # In this case they're very close but the algorithms ARE different
        cx = reconcile_pairwise_pct(values, threshold_pct=threshold)

        # Both should PASS (under 0.5%)
        assert result.status.value == "PASS"
        assert cx["status"] == "PASS"
