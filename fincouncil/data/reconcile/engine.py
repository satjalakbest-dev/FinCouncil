"""Reconcile engine — compare a field across providers and flag discrepancies.

Usage::

    from fincouncil.data.reconcile.engine import ReconcileEngine

    engine = ReconcileEngine()
    result = engine.reconcile(
        symbol="NYSE:AAPL",
        field="close",
        as_of=date(2026, 6, 2),
        currency="USD",
        values_by_source={
            "openbb": 195.50,
            "yfinance": 195.48,
        },
        record_type="price",
    )
    assert not result.flagged  # within 0.5%

Design contract (CP1 / T1.8):
- Price threshold: 0.5%
- Fundamentals threshold: 1.0%
- Injected discrepancies MUST be flagged (never swallowed).
- Every reconciliation writes a ``ReconcileResult`` that can be persisted.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fincouncil.data.schema import (
    RECONCILE_THRESHOLD_FUNDAMENTALS_PCT,
    RECONCILE_THRESHOLD_PRICE_PCT,
    RecordType,
    ReconcileResult,
)


class ReconcileEngine:
    """Compare a single data point across providers and flag discrepancies.

    The engine is stateless — it does not persist results itself.
    The caller (or the store layer) is responsible for writing
    ``ReconcileResult`` objects to the ``reconcile_log`` table.
    """

    def reconcile(
        self,
        symbol: str,
        field: str,
        as_of: date,
        currency: str,
        values_by_source: dict[str, float],
        record_type: str = "price",
        *,
        price_threshold_pct: float = RECONCILE_THRESHOLD_PRICE_PCT,
        fundamentals_threshold_pct: float = RECONCILE_THRESHOLD_FUNDAMENTALS_PCT,
    ) -> ReconcileResult:
        """Compare values from ≥2 sources and return a ``ReconcileResult``.

        Parameters
        ----------
        symbol:
            Canonical symbol (e.g. ``"NYSE:AAPL"``).
        field:
            Field name being reconciled (e.g. ``"close"``, ``"revenue"``).
        as_of:
            Reference date for the data point.
        currency:
            ISO-4217 currency code.
        values_by_source:
            Mapping of provider name → value.  Must contain ≥2 entries
            for a meaningful comparison.
        record_type:
            ``"price"`` or ``"fundamentals"`` — determines which
            threshold applies.
        price_threshold_pct:
            Override the default price threshold (for testing).
        fundamentals_threshold_pct:
            Override the default fundamentals threshold (for testing).

        Returns
        -------
        ReconcileResult
            Includes ``flagged`` (bool), ``diff_pct``, and ``explanation``.

        Notes
        -----
        - If fewer than 2 sources are provided, ``flagged`` is False and
          ``diff_pct`` is None with an explanatory note.
        - Percentage diff = ``|max - min| / mean * 100``.
        - A flagged result is never demoted — once the diff exceeds the
          threshold, it is recorded truthfully.
        """
        if len(values_by_source) < 2:
            return ReconcileResult(
                symbol=symbol,
                field=field,
                as_of=as_of,
                currency=currency,
                values=values_by_source,
                diff_pct=None,
                flagged=False,
                explanation=f"Only {len(values_by_source)} source(s); "
                            f"reconciliation requires ≥2.",
            )

        vals = list(values_by_source.values())
        max_val = max(vals)
        min_val = min(vals)
        mean_val = (max_val + min_val) / 2

        # Guard against division by zero
        if mean_val == 0:
            diff_pct = 0.0 if max_val == 0 else float("inf")
        else:
            diff_pct = abs(max_val - min_val) / abs(mean_val) * 100

        threshold = (
            fundamentals_threshold_pct
            if record_type == "fundamentals"
            else price_threshold_pct
        )

        flagged = diff_pct > threshold

        explanation = self._explain(
            values_by_source, diff_pct, threshold, flagged, field
        )

        return ReconcileResult(
            symbol=symbol,
            field=field,
            as_of=as_of,
            currency=currency,
            values=dict(values_by_source),
            diff_pct=diff_pct,
            flagged=flagged,
            explanation=explanation,
        )

    @staticmethod
    def _explain(
        values_by_source: dict[str, float],
        diff_pct: float,
        threshold: float,
        flagged: bool,
        field: str,
    ) -> str:
        """Generate a human-readable explanation for the reconcile outcome."""
        sources_str = ", ".join(
            f"{src}={val:.6g}" for src, val in values_by_source.items()
        )
        if flagged:
            return (
                f"DISCREPANCY on '{field}': {sources_str} "
                f"(diff={diff_pct:.4f}%, threshold={threshold:.1f}%)"
            )
        return (
            f"OK on '{field}': {sources_str} "
            f"(diff={diff_pct:.4f}% ≤ threshold={threshold:.1f}%)"
        )
