"""Normalize macro provider payloads into canonical records."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from fincouncil.data.schema import CurrencyCode, MacroRecord, validate_record


def _date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise ValueError(f"unsupported date value: {value!r}")


def normalize_macro_records(rows: Iterable[Mapping[str, Any]], *, source: str, indicator: str, unit: str, region: str, frequency: str, as_of: datetime | None = None, currency: str | None = None, series_id: str | None = None) -> list[MacroRecord]:
    stamp = as_of or datetime.now(timezone.utc)
    normalized: list[MacroRecord] = []
    for row in rows:
        raw_value = row.get("value")
        if raw_value in (None, ".", ""):
            continue
        rec = MacroRecord(
            source=str(row.get("source") or source),
            as_of=stamp,
            indicator=str(row.get("indicator") or indicator),
            value=Decimal(str(raw_value)),
            unit=str(row.get("unit") or unit),
            region=str(row.get("region") or region),
            frequency=str(row.get("frequency") or frequency),
            observation_date=_date(row.get("observation_date") or row.get("date")),
            currency=CurrencyCode(currency) if currency else None,
            series_id=row.get("series_id") or series_id,
        )
        validate_record(rec)
        normalized.append(rec)
    return normalized
