"""Reconcile engine — cross-source verification for financial data.

This is the core of the data moat. Every significant number (price, key
fundamental line items) MUST be compared across ≥2 sources. Discrepancies
exceeding the threshold are FLAGGED, never swallowed.

Reference: DATA_SOURCES.md "Reconcile / Verify Policy"
           PHASE1_DATA_LAYER_SPRINT.md T1.8
"""
