"""Normalize news and sentiment provider payloads into canonical records."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from fincouncil.data.schema import NewsRecord, SentimentRecord, validate_record


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"unsupported datetime value: {value!r}")


def normalize_news_records(rows: Iterable[Mapping[str, Any]], *, source: str, as_of: datetime | None = None, symbol: str | None = None) -> list[NewsRecord]:
    normalized: list[NewsRecord] = []
    stamp = as_of or datetime.now(timezone.utc)
    for row in rows:
        rec = NewsRecord(
            source=str(row.get("source") or source),
            as_of=stamp,
            headline=str(row.get("headline") or row.get("title") or row.get("summary") or "").strip(),
            published_at=_dt(row.get("published_at") or row.get("datetime") or row.get("time") or stamp),
            url=row.get("url"),
            symbol=row.get("symbol") or symbol,
            category=row.get("category"),
            provider_id=str(row.get("id")) if row.get("id") is not None else row.get("provider_id"),
            summary=row.get("summary"),
        )
        validate_record(rec)
        normalized.append(rec)
    return normalized


def normalize_sentiment_records(rows: Iterable[Mapping[str, Any]], *, source: str, symbol: str, as_of: datetime | None = None) -> list[SentimentRecord]:
    normalized: list[SentimentRecord] = []
    stamp = as_of or datetime.now(timezone.utc)
    for row in rows:
        score = Decimal(str(row.get("score", row.get("sentiment", 0))))
        rec = SentimentRecord(
            source=str(row.get("source") or source),
            as_of=stamp,
            symbol=str(row.get("symbol") or symbol),
            score=score,
            scale_min=Decimal(str(row.get("scale_min", "-1"))),
            scale_max=Decimal(str(row.get("scale_max", "1"))),
            observed_at=_dt(row.get("observed_at") or row.get("atTime") or stamp),
            channel=str(row.get("channel") or row.get("source_channel") or "aggregate"),
            label=row.get("label"),
        )
        validate_record(rec)
        normalized.append(rec)
    return normalized
