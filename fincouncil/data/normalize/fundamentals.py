"""Phase 2 fundamentals normalization placeholders for optional providers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def pass_raw_fundamentals(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return shallow raw fundamentals rows without inventing financial fields."""
    return [dict(row) for row in rows]
