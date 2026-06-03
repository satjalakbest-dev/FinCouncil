"""FinCouncil data layer — canonical schema, adapters, normalize, reconcile, store.

This namespace owns the data moat: every financial number that enters the
research council MUST come through this layer, carry a ``source`` and
``currency`` tag, and be reconcilable across providers.

Design contract (see PHASE1_DATA_LAYER_SPRINT.md T1.1):
- Every record has ``source``, ``currency``, ``as_of``.
- Price records: date, o/h/l/c/volume, adjusted_close.
- Fundamentals records: period (FY/Q), fiscal_date, standard line items + ratios.
- Reconcile log: symbol, field, date, values-per-source, diff, flagged, explanation.
"""
