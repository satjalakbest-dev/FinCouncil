"""Normalization layer — raw provider output → canonical schema records.

Every adapter returns raw dicts/DataFrames. This layer converts them to
validated ``CanonicalRecord`` subclasses. All records carry ``source`` and
``as_of``; monetary records carry ``currency`` and macro records carry
explicit ``unit``.

Design reference: PHASE1_DATA_LAYER_SPRINT.md T1.6
"""

from .price import NormalizationError, normalize_price_record, normalize_price_records

__all__ = ["NormalizationError", "normalize_price_record", "normalize_price_records"]
