"""Normalization layer — raw provider output → canonical schema records.

Every adapter returns raw dicts/DataFrames. This layer converts them to
validated ``CanonicalRecord`` subclasses with mandatory ``source``,
``currency``, and ``as_of`` fields.

Design reference: PHASE1_DATA_LAYER_SPRINT.md T1.6
"""

from .price import NormalizationError, normalize_price_record, normalize_price_records

__all__ = ["NormalizationError", "normalize_price_record", "normalize_price_records"]
