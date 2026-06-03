"""Cache manager for read-local-first data access pattern.

The CacheManager provides a caching layer between adapters and the warehouse,
implementing:
- Local-first reads (check DuckDB before adapter calls)
- TTL-based freshness checks
- Idempotent writes via warehouse upsert
- Canonical record normalization

This ensures fast, auditable data access with proper source attribution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fincouncil.data.adapters.base import BaseAdapter
from fincouncil.data.normalize.price import normalize_price_records
from fincouncil.data.schema import CurrencyCode, PriceRecord, validate_record
from fincouncil.data.store.warehouse import DuckDBWarehouse


@dataclass(frozen=True, kw_only=True)
class CachePolicy:
    """Configurable cache TTL policy for different data types."""

    default_max_age_hours: int = 24
    eod_prices_max_age_hours: int = 24
    fundamentals_max_age_hours: int = 24 * 7  # Fundamentals change less often

    def max_age_for(self, data_type: str) -> timedelta:
        """Return TTL for a given data type."""
        if data_type == "price":
            return timedelta(hours=self.eod_prices_max_age_hours)
        if data_type == "fundamentals":
            return timedelta(hours=self.fundamentals_max_age_hours)
        return timedelta(hours=self.default_max_age_hours)


class CacheManager:
    """Cache manager implementing read-local-first pattern.

    The cache manager checks local DuckDB storage before calling adapters,
    and writes normalized results back to the warehouse for future reads.
    Freshness is determined by the ``updated_at`` timestamp managed by
    the warehouse.

    Example:
        >>> warehouse = DuckDBWarehouse(":memory:")
        >>> cache = CacheManager(warehouse)
        >>> adapter = OpenBBAdapter()
        >>> prices = cache.get_or_fetch(
        ...     "US:AAPL", date(2024, 1, 1), date(2024, 1, 31),
        ...     adapter, "USD", "openbb:yfinance"
        ... )
    """

    def __init__(
        self,
        warehouse: DuckDBWarehouse,
        *,
        policy: CachePolicy | None = None,
    ) -> None:
        """Initialize cache manager with warehouse and optional policy.

        Args:
            warehouse: DuckDB warehouse for cache storage.
            policy: Cache TTL policy; defaults to 24h for EOD prices.
        """
        self._warehouse = warehouse
        self._policy = policy or CachePolicy()

    def get_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read cached prices for a symbol and date range.

        Args:
            symbol: Canonical symbol (e.g., "US:AAPL").
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            source: Optional data source filter (e.g., "openbb:yfinance").

        Returns:
            List of price row dicts as stored in the warehouse.
            Empty list if no cached data exists.
        """
        frame = self._warehouse.query_prices(
            symbol=symbol,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            source=source,
        )
        return frame.to_dict(orient="records")

    def put_prices(self, records: list[PriceRecord]) -> int:
        """Write normalized price records to cache via warehouse upsert.

        Args:
            records: List of canonical PriceRecord objects.

        Returns:
            Number of records written.

        Raises:
            ValueError: If records fail validation or warehouse write fails.
        """
        if not records:
            return 0

        # Validate all records before writing
        for record in records:
            validate_record(record)

        # Convert to warehouse-compatible dicts
        rows = [
            {
                "symbol": record.symbol,
                "date": record.date,
                "open": float(record.open),
                "high": float(record.high),
                "low": float(record.low),
                "close": float(record.close),
                "volume": record.volume,
                "currency": str(record.currency),
                "source": record.source,
            }
            for record in records
        ]

        return self._warehouse.upsert_prices(rows)

    def is_fresh(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        source: str,
        *,
        max_age_hours: int | None = None,
    ) -> bool:
        """Check if cached data for a symbol/date/source is still fresh.

        Freshness is determined by the ``updated_at`` timestamp in the warehouse.
        Data is considered fresh if the most recent update is within the TTL.

        Args:
            symbol: Canonical symbol.
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            source: Data source (e.g., "openbb:yfinance").
            max_age_hours: Override default TTL; uses policy if None.

        Returns:
            True if cached data exists and is within TTL, False otherwise.
        """
        rows = self.get_prices(symbol, start_date, end_date, source=source)
        if not rows:
            return False

        # For now, we check freshness at the cache key level
        # (symbol, date range, source). If any data exists, we consider
        # the key present. A more sophisticated version would check per-row.
        ttl_hours = max_age_hours if max_age_hours is not None else self._policy.eod_prices_max_age_hours

        # TTL of 0 or negative means data is always stale
        if ttl_hours <= 0:
            return False

        cutoff = datetime.now() - timedelta(hours=ttl_hours)

        # Check if we have ANY rows with updated_at within TTL
        # Note: DuckDBWarehouse.query_prices doesn't return updated_at,
        # so we need to query directly
        params = [symbol, start_date.isoformat(), end_date.isoformat(), source, cutoff]
        result = self._warehouse._connection.execute(
            """
            SELECT COUNT(*) as count
            FROM prices
            WHERE symbol = ?
              AND date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
              AND source = ?
              AND updated_at >= ?
            """,
            params,
        ).fetchone()

        if result is None:
            return False
        return int(result[0]) > 0

    def get_or_fetch(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adapter: BaseAdapter,
        currency: str | CurrencyCode,
        source: str,
        *,
        force_refresh: bool = False,
    ) -> list[PriceRecord]:
        """Read-local-first: check cache, fetch if stale/missing, cache and return.

        This is the primary cache interface. It implements the read-local-first
        pattern by checking the cache first, and only calling the adapter if
        data is missing or stale.

        Args:
            symbol: Canonical symbol (e.g., "US:AAPL").
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            adapter: Data source adapter to call on cache miss.
            currency: ISO currency code for the data.
            source: Data source identifier (e.g., "openbb:yfinance").
            force_refresh: If True, bypass cache and call adapter.

        Returns:
            List of canonical PriceRecord objects.

        Raises:
            ValueError: If adapter returns invalid data or normalization fails.
        """
        if not force_refresh and self.is_fresh(symbol, start_date, end_date, source):
            # Cache hit: read and normalize cached rows
            raw_rows = self.get_prices(symbol, start_date, end_date, source=source)
            return _normalize_cached_rows(raw_rows, symbol, currency)

        # Cache miss or stale: fetch from adapter
        raw_payload = adapter.get_price(symbol, start_date, end_date)

        if not raw_payload:
            # Adapter returned nothing; return empty list
            return []

        # Normalize to canonical records
        records = normalize_price_records(
            raw_payload,
            symbol=symbol,
            source=source,
            currency=str(currency),
            as_of=datetime.now().isoformat(),
        )

        # Cache the normalized records
        self.put_prices(records)

        return records


def _normalize_cached_rows(
    rows: list[dict[str, Any]],
    symbol: str,
    currency: str | CurrencyCode,
) -> list[PriceRecord]:
    """Convert cached warehouse rows back to canonical PriceRecord objects.

    Warehouse rows are simpler than adapter payloads (no provider metadata),
    so we reconstruct with cached values and current as_of timestamp.
    """
    currency_code = CurrencyCode(str(currency))
    records: list[PriceRecord] = []

    for row in rows:
        # Warehouse rows have float values; convert back to Decimal
        record = PriceRecord(
            kind="price",
            symbol=row["symbol"],
            date=_parse_date(row["date"]),
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            volume=int(row["volume"]),
            adjusted_close=Decimal(str(row["close"])),  # Cache stores close only
            source=row["source"],
            currency=currency_code,
            as_of=datetime.now(),
        )
        validate_record(record)
        records.append(record)

    return records


def _parse_date(value: date | str) -> date:
    """Parse date from warehouse row."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Cannot parse date from {type(value)}")
