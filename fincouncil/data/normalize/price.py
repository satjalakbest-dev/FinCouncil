"""Price normalization helpers for mocked adapter payloads.

T1.6 scope is intentionally provider-call free: callers pass raw adapter
payloads that were already fetched elsewhere, and these helpers return
validated canonical ``PriceRecord`` objects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fincouncil.data.schema import CurrencyCode, PriceRecord, validate_record

_DATE_FIELDS = ("date", "as_of")
_PRICE_FIELDS = ("open", "high", "low", "close", "adjusted_close")


class NormalizationError(ValueError):
    """Raised when a raw provider payload cannot become a canonical record."""


def normalize_price_record(
    raw: Mapping[str, Any],
    *,
    symbol: str,
    source: str,
    currency: str,
    as_of: date | datetime | str,
    adjusted_close_policy: str = "close_when_missing",
) -> PriceRecord:
    """Convert one raw EOD price payload to a canonical ``PriceRecord``.

    Adjusted-close semantics:
    - If the raw payload contains ``adjusted_close``/``adj_close``/``adjclose``,
      that explicit provider value is used.
    - If it is absent and ``adjusted_close_policy`` is ``"close_when_missing"``
      (the default), ``adjusted_close`` is set equal to ``close`` so downstream
      consumers have one stable adjusted-price field.
    - If the policy is ``"require"``, missing adjusted close raises
      ``NormalizationError``.
    """
    trade_date = _parse_date(_required(raw, "date"), field_name="date")
    close = _decimal(_required(raw, "close"), field_name="close")
    adjusted_close = _extract_adjusted_close(raw, close, adjusted_close_policy)

    record = PriceRecord(
        symbol=symbol,
        date=trade_date,
        open=_decimal(_required(raw, "open"), field_name="open"),
        high=_decimal(_required(raw, "high"), field_name="high"),
        low=_decimal(_required(raw, "low"), field_name="low"),
        close=close,
        volume=_int(_required(raw, "volume"), field_name="volume"),
        adjusted_close=adjusted_close,
        source=source,
        currency=CurrencyCode(currency),
        as_of=_parse_date_or_datetime(as_of, field_name="as_of"),
    )
    validate_record(record)
    return record


def normalize_price_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    symbol: str,
    source: str,
    currency: str,
    as_of: date | datetime | str,
    adjusted_close_policy: str = "close_when_missing",
) -> list[PriceRecord]:
    """Normalize a batch of raw EOD price payloads preserving input order."""
    return [
        normalize_price_record(
            row,
            symbol=symbol,
            source=source,
            currency=currency,
            as_of=as_of,
            adjusted_close_policy=adjusted_close_policy,
        )
        for row in rows
    ]


def _extract_adjusted_close(
    raw: Mapping[str, Any],
    close: Decimal,
    policy: str,
) -> Decimal:
    for key in ("adjusted_close", "adj_close", "adjclose"):
        value = raw.get(key)
        if value is not None:
            return _decimal(value, field_name=key)
    if policy == "close_when_missing":
        return close
    if policy == "require":
        raise NormalizationError("adjusted_close is required by policy")
    raise NormalizationError(f"unknown adjusted_close_policy: {policy}")


def _required(raw: Mapping[str, Any], field_name: str) -> Any:
    value = raw.get(field_name)
    if value is None:
        raise NormalizationError(f"raw price payload missing required field: {field_name}")
    return value


def _parse_date_or_datetime(value: date | datetime | str, *, field_name: str) -> date | datetime:
    if isinstance(value, datetime):
        return value
    return _parse_date(value, field_name=field_name)


def _parse_date(value: date | datetime | str, *, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise NormalizationError(f"{field_name} must be ISO date-like") from exc
    raise NormalizationError(f"{field_name} must be date, datetime, or ISO date string")


def _decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise NormalizationError(f"{field_name} must be numeric") from exc


def _int(value: Any, *, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise NormalizationError(f"{field_name} must be non-negative")
    return parsed
