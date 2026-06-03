"""Reconcile engine — compare a field across providers and flag discrepancies.

The engine is the core of the data moat (T1.8). Every significant number
(price, key fundamental line items) is compared across ≥2 sources.
Discrepancies exceeding the threshold are flagged, **never swallowed**.

The engine produces canonical ``ReconcileLogRecord`` objects that can be
persisted to the ``reconcile_log`` table via the store layer.

Reference: DATA_SOURCES.md "Reconcile / Verify Policy"
           PHASE1_DATA_LAYER_SPRINT.md T1.8

Thresholds:
- Price EOD: 0.5%
- Fundamentals: 1.0%

Usage::

    from fincouncil.data.reconcile.engine import ReconcileEngine

    engine = ReconcileEngine()
    record = engine.reconcile(
        symbol="NASDAQ:AAPL",
        field="close",
        as_of=date(2026, 6, 2),
        currency="USD",
        values_by_source={
            "openbb": Decimal("195.50"),
            "yfinance": Decimal("195.48"),
        },
        record_kind="price",
    )
    assert record.status == ReconcileStatus.PASS
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from fincouncil.data.schema import (
    CurrencyCode,
    ReconcileLogRecord,
    ReconcileStatus,
)

# Default thresholds (from DATA_SOURCES.md)
DEFAULT_PRICE_THRESHOLD_PCT = Decimal("0.5")
DEFAULT_FUNDAMENTALS_THRESHOLD_PCT = Decimal("1.0")


class InsufficientSourcesError(ValueError):
    """Raised when reconcile is called with fewer than 2 sources."""


class ReconcileEngine:
    """Compare a single data point across providers and flag discrepancies.

    The engine is stateless — it does not persist results itself.
    The caller (or the store layer) is responsible for writing
    ``ReconcileLogRecord`` objects to the ``reconcile_log`` table.

    All monetary values use ``Decimal`` for precision.
    """

    def reconcile(
        self,
        symbol: str,
        field: str,
        as_of: date,
        currency: CurrencyCode,
        values_by_source: Mapping[str, Decimal],
        record_kind: str = "price",
        *,
        price_threshold_pct: Decimal = DEFAULT_PRICE_THRESHOLD_PCT,
        fundamentals_threshold_pct: Decimal = DEFAULT_FUNDAMENTALS_THRESHOLD_PCT,
    ) -> ReconcileLogRecord:
        """Compare values from ≥2 sources and return a ``ReconcileLogRecord``.

        Parameters
        ----------
        symbol:
            Canonical symbol (e.g. ``"NASDAQ:AAPL"``).
        field:
            Field name being reconciled (e.g. ``"close"``, ``"revenue"``).
        as_of:
            Reference date for the data point.
        currency:
            ISO-4217 currency code (``CurrencyCode``).
        values_by_source:
            Mapping of provider name → value.  Must contain ≥2 entries
            for a meaningful comparison.
        record_kind:
            ``"price"`` or ``"fundamentals"`` — determines which
            threshold applies.
        price_threshold_pct:
            Override the default price threshold (for testing).
        fundamentals_threshold_pct:
            Override the default fundamentals threshold (for testing).

        Returns
        -------
        ReconcileLogRecord
            A canonical record suitable for persisting to ``reconcile_log``.

        Raises
        ------
        InsufficientSourcesError
            If fewer than 2 sources are provided.

        Notes
        -----
        - Percentage diff = ``|max - min| / mean * 100``.
        - A flagged result is never demoted — once the diff exceeds the
          threshold, it is recorded truthfully.
        - Uses ``Decimal`` arithmetic throughout for financial precision.
        """
        if len(values_by_source) < 2:
            raise InsufficientSourcesError(
                f"Reconciliation requires ≥2 sources, got {len(values_by_source)}"
            )

        threshold = (
            fundamentals_threshold_pct
            if record_kind == "fundamentals"
            else price_threshold_pct
        )

        vals = list(values_by_source.values())
        max_val = max(vals)
        min_val = min(vals)
        mean_val = (max_val + min_val) / 2

        # Guard against division by zero
        if mean_val == 0:
            diff_pct = Decimal("0") if max_val == 0 else Decimal("Infinity")
        else:
            diff_pct = abs(max_val - min_val) / abs(mean_val) * 100

        status = ReconcileStatus.FLAG if diff_pct > threshold else ReconcileStatus.PASS

        explanation = self._explain(
            values_by_source, diff_pct, threshold, status, field
        )

        return ReconcileLogRecord(
            source="reconcile_engine",
            currency=currency,
            as_of=as_of,
            symbol=symbol,
            field=field,
            date=as_of,
            values=dict(values_by_source),
            diff_pct=diff_pct,
            threshold_pct=threshold,
            status=status,
            explanation=explanation,
        )

    @staticmethod
    def _explain(
        values_by_source: Mapping[str, Decimal],
        diff_pct: Decimal,
        threshold: Decimal,
        status: ReconcileStatus,
        field: str,
    ) -> str:
        """Generate a human-readable explanation for the reconcile outcome."""
        sources_str = ", ".join(
            f"{src}={val}" for src, val in values_by_source.items()
        )
        if status == ReconcileStatus.FLAG:
            return (
                f"DISCREPANCY on '{field}': {sources_str} "
                f"(diff={diff_pct:.4f}%, threshold={threshold:.1f}%)"
            )
        return (
            f"OK on '{field}': {sources_str} "
            f"(diff={diff_pct:.4f}% ≤ threshold={threshold:.1f}%)"
        )
