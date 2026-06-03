"""FinCouncil caching layer for read-local-first data access.

The cache layer sits between adapters and the warehouse, providing:
- Read-local-first pattern (check cache before adapter)
- TTL-based freshness checks
- Idempotent writes via warehouse upsert
- Canonical record normalization

This keeps the data layer fast and auditable: every cache hit has a source
and as_of timestamp, and stale data triggers fresh adapter calls.
"""

from __future__ import annotations

from fincouncil.data.cache.manager import CacheManager

__all__ = ["CacheManager"]
