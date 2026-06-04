"""Explicit provider fallback helpers with auditable provenance."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fincouncil.data.adapters.akshare import AkShareAdapter, AkShareAdapterError
from fincouncil.data.adapters.yfinance import YFinanceAdapter
from fincouncil.data.schema import ProviderGapRecord, validate_record


def get_price_with_akshare_yfinance_fallback(
    symbol: str,
    start: date,
    end: date,
    *,
    akshare_adapter: Any | None = None,
    yfinance_adapter: Any | None = None,
) -> tuple[list[dict[str, Any]], ProviderGapRecord | None]:
    """Fetch CN/HK prices from AkShare, falling back to yfinance explicitly.

    Returns provider rows and an optional ``ProviderGapRecord`` when fallback is
    used. The fallback audit is returned to the caller so it can be persisted in
    ``provider_gap_log``; failures are never swallowed silently.
    """
    primary = akshare_adapter or AkShareAdapter()
    fallback = yfinance_adapter or YFinanceAdapter()
    try:
        rows = primary.get_price(symbol, start, end)
        return rows, None
    except Exception as exc:
        fallback_rows = fallback.get_price(symbol, start, end)
        audit = ProviderGapRecord(
            source="fallback:akshare_to_yfinance",
            as_of=datetime.now(timezone.utc),
            status="FALLBACK_USED",
            primary_source="akshare",
            fallback_source="yfinance",
            error_type=type(exc).__name__,
            failure_reason=str(exc),
            symbol=symbol,
            market=symbol.split(":", 1)[0] if ":" in symbol else None,
            record_count=len(fallback_rows),
        )
        validate_record(audit)
        annotated = []
        for row in fallback_rows:
            record = dict(row)
            record["source"] = "fallback:akshare_to_yfinance"
            record["primary_source"] = "akshare"
            record["fallback_source"] = "yfinance"
            annotated.append(record)
        return annotated, audit
