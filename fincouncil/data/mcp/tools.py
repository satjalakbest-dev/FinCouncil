"""MCP tool functions for FinCouncil data layer.

These are thin orchestration functions that compose the data pipeline:
adapters → normalize → cache → warehouse.

Each tool returns canonical records with source/currency/as_of fields.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fincouncil.data.adapters.base import BaseAdapter
from fincouncil.data.adapters.openbb import OpenBBAdapter
from fincouncil.data.adapters.yfinance import YFinanceAdapter
from fincouncil.data.cache.manager import CacheManager
from fincouncil.data.reconcile.engine import ReconcileEngine
from fincouncil.data.schema import CurrencyCode, PriceRecord
from fincouncil.data.symbols.mapping import supported_exchanges


class MCPToolError(RuntimeError):
    """Base error for MCP tool failures."""


class DataNotAvailableError(MCPToolError):
    """Raised when requested data is not available from any source."""


class InvalidParameterError(MCPToolError):
    """Raised when MCP tool parameters are invalid."""


def get_price(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    cache_manager: CacheManager | None = None,
    warehouse: Any | None = None,
    source: str | None = None,
    currency: str = "USD",
) -> list[dict[str, Any]]:
    """Get EOD price data for a symbol.

    Args:
        symbol: Canonical symbol (e.g., "US:AAPL", "SET:PTT").
        start_date: ISO date string (inclusive).
        end_date: ISO date string (inclusive).
        cache_manager: Optional CacheManager for caching. If None, creates one with warehouse.
        warehouse: Optional warehouse for CacheManager. Required if cache_manager is None.
        source: Optional data source filter (e.g., "openbb:yfinance").
        currency: ISO currency code (default: "USD").

    Returns:
        List of canonical PriceRecord dicts with source/currency/as_of fields.

    Raises:
        InvalidParameterError: If parameters are invalid.
        DataNotAvailableError: If no data is available.
    """
    _validate_dates(start_date, end_date)
    _validate_symbol(symbol)

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    # If no source specified, use yfinance as default
    if source is None:
        source = "yfinance:yfinance"

    # Setup cache manager if not provided
    if cache_manager is None:
        if warehouse is None:
            raise InvalidParameterError("warehouse is required when cache_manager is not provided")
        from fincouncil.data.store.warehouse import DuckDBWarehouse

        if not isinstance(warehouse, DuckDBWarehouse):
            warehouse = DuckDBWarehouse(str(warehouse))
        cache_manager = CacheManager(warehouse)

    # Use YFinance adapter as default (OpenBB optional)
    adapter = YFinanceAdapter()

    # Fetch prices via cache manager
    try:
        records = cache_manager.get_or_fetch(
            symbol=symbol,
            start_date=start,
            end_date=end,
            adapter=adapter,
            currency=CurrencyCode(currency),
            source=source,
        )
    except Exception as exc:
        raise DataNotAvailableError(f"Failed to fetch price data for {symbol}") from exc

    if not records:
        raise DataNotAvailableError(f"No price data available for {symbol} in date range")

    # Convert dataclass records to dicts for MCP serialization
    return [_record_to_dict(record) for record in records]


def get_fundamentals(
    symbol: str,
    period: str = "FY",
    *,
    adapter: BaseAdapter | None = None,
) -> list[dict[str, Any]]:
    """Get fundamental data for a symbol.

    Args:
        symbol: Canonical symbol (e.g., "US:AAPL").
        period: Financial statement period ("FY" or "Q", default: "FY").
        adapter: Optional data adapter. If None, uses yfinance.

    Returns:
        List of canonical FundamentalsRecord dicts.

    Raises:
        InvalidParameterError: If parameters are invalid.
        DataNotAvailableError: If no data is available.
        NotImplementedError: Phase 1 scope is price-only for second source.
    """
    _validate_symbol(symbol)
    _validate_period(period)

    # Use yfinance adapter as default (has real fundamentals implementation)
    if adapter is None:
        adapter = YFinanceAdapter()

    if not adapter.is_available():
        raise DataNotAvailableError(f"Fundamentals adapter not available for {symbol}")

    try:
        raw_records = adapter.get_fundamentals(symbol, period=period)
    except NotImplementedError as exc:
        raise NotImplementedError(
            "Fundamentals not yet fully implemented — Phase 1 scope is price-only"
        ) from exc
    except Exception as exc:
        raise DataNotAvailableError(f"Failed to fetch fundamentals for {symbol}") from exc

    if not raw_records:
        raise DataNotAvailableError(f"No fundamentals available for {symbol}")

    # Return raw records for now — normalization will be added in future phases
    return list(raw_records)


def list_symbols(exchange: str = "US") -> list[dict[str, Any]]:
    """List supported symbols for an exchange.

    Args:
        exchange: Exchange code (e.g., "US", "SET", "TSE", "HKEX"). Default: "US".

    Returns:
        List of symbol metadata dicts.

    Raises:
        InvalidParameterError: If exchange is not supported.
    """
    _validate_exchange(exchange)

    # Get supported exchanges from symbols module
    supported = supported_exchanges()

    if exchange not in supported:
        raise InvalidParameterError(f"Unsupported exchange: {exchange}")

    # For now, return a placeholder. In production, this would query
    # the symbol registry or database for the exchange's symbol list.
    return [
        {
            "exchange": exchange,
            "symbol": f"{exchange}:EXAMPLE",
            "name": "Example placeholder",
            "currency": "USD",
            "status": "active",
        }
    ]


def reconcile(
    symbol: str,
    field: str,
    trade_date: str,
    *,
    cache_manager: CacheManager | None = None,
    warehouse: Any | None = None,
    reconcile_engine: ReconcileEngine | None = None,
) -> dict[str, Any]:
    """Reconcile a data field across multiple sources.

    Args:
        symbol: Canonical symbol (e.g., "US:AAPL").
        field: Field to reconcile (e.g., "close", "high", "low").
        trade_date: ISO date string for the trade date.
        cache_manager: Optional CacheManager for data fetching.
        warehouse: Optional warehouse for CacheManager.
        reconcile_engine: Optional ReconcileEngine. If None, creates default.

    Returns:
        ReconcileLogRecord dict with reconcile results.

    Raises:
        InvalidParameterError: If parameters are invalid.
        DataNotAvailableError: If insufficient sources for reconciliation.
    """
    _validate_symbol(symbol)
    _validate_trade_date(trade_date)
    _validate_price_field(field)

    date_obj = date.fromisoformat(trade_date)

    # Setup cache manager if not provided
    if cache_manager is None:
        if warehouse is None:
            raise InvalidParameterError("warehouse is required when cache_manager is not provided")
        from fincouncil.data.store.warehouse import DuckDBWarehouse

        if not isinstance(warehouse, DuckDBWarehouse):
            warehouse = DuckDBWarehouse(str(warehouse))
        cache_manager = CacheManager(warehouse)

    # Setup reconcile engine if not provided
    if reconcile_engine is None:
        reconcile_engine = ReconcileEngine()

    # Fetch from both sources (OpenBB optional, YFinance required)
    adapters = [("yfinance", YFinanceAdapter()), ("openbb", OpenBBAdapter())]
    values_by_source: dict[str, Decimal] = {}

    for source_name, adapter in adapters:
        if not adapter.is_available():
            continue

        try:
            records = cache_manager.get_or_fetch(
                symbol=symbol,
                start_date=date_obj,
                end_date=date_obj,
                adapter=adapter,
                currency=CurrencyCode("USD"),
                source=f"{source_name}:yfinance",
            )
            if records:
                # Get the value for the specified field from the first record
                record = records[0]
                value = getattr(record, field, None)
                if value is not None:
                    values_by_source[source_name] = value
        except Exception:
            # Skip unavailable or failing sources
            continue

    if len(values_by_source) < 2:
        raise DataNotAvailableError(
            f"Insufficient sources for reconciliation: {len(values_by_source)} available, need 2+"
        )

    # Perform reconciliation
    try:
        reconcile_record = reconcile_engine.reconcile(
            symbol=symbol,
            field=field,
            as_of=date_obj,
            currency=CurrencyCode("USD"),
            values_by_source=values_by_source,
            record_kind="price",
        )
    except Exception as exc:
        raise MCPToolError(f"Reconciliation failed for {symbol} {field} on {trade_date}") from exc

    # Persist result to reconcile_log table (both PASS and FLAG)
    _wh = getattr(cache_manager, "_warehouse", None)
    if _wh is not None:
        _persist_reconcile_result(reconcile_record, _wh)

    return _record_to_dict(reconcile_record)


def _validate_dates(start_date: str, end_date: str) -> None:
    """Validate date parameters."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start > end:
            raise InvalidParameterError("start_date must be on or before end_date")
    except ValueError as exc:
        raise InvalidParameterError(f"Invalid date format: {exc}") from exc


def _validate_symbol(symbol: str) -> None:
    """Validate symbol parameter."""
    if not symbol or not symbol.strip():
        raise InvalidParameterError("symbol must not be empty")


def _validate_period(period: str) -> None:
    """Validate period parameter."""
    from fincouncil.data.schema import Period

    if period not in Period.__members__:
        raise InvalidParameterError(f"Invalid period: {period}. Must be 'FY' or 'Q'")


def _validate_exchange(exchange: str) -> None:
    """Validate exchange parameter."""
    if not exchange or not exchange.strip():
        raise InvalidParameterError("exchange must not be empty")


def _validate_trade_date(trade_date: str) -> None:
    """Validate trade_date parameter."""
    try:
        date.fromisoformat(trade_date)
    except ValueError as exc:
        raise InvalidParameterError(f"Invalid trade_date format: {exc}") from exc


def _validate_price_field(field: str) -> None:
    """Validate field parameter for price reconciliation."""
    valid_fields = {"open", "high", "low", "close", "adjusted_close"}
    if field not in valid_fields:
        raise InvalidParameterError(f"Invalid field: {field}. Must be one of {valid_fields}")


def _record_to_dict(record: Any) -> dict[str, Any]:
    """Convert a dataclass record to dict for MCP serialization."""
    if hasattr(record, "model_dump"):
        return record.model_dump()
    if hasattr(record, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(record)
    return dict(record)


def _persist_reconcile_result(record: Any, warehouse: Any) -> None:
    """Persist a ReconcileLogRecord to the warehouse reconcile_log table.

    Writes both PASS and FLAG results so the log is a complete audit trail.
    Failures to persist are logged but do not block the reconcile response.
    """
    import uuid
    from datetime import datetime

    try:
        row = {
            "run_id": str(uuid.uuid4()),
            "symbol": record.symbol,
            "source": record.source,
            "status": str(record.status.value) if hasattr(record.status, "value") else str(record.status),
            "message": record.explanation,
            "created_at": datetime.now().isoformat(),
        }
        warehouse.upsert_reconcile_log([row])
    except Exception:
        # Persistence failure must not block reconcile response
        import logging
        logging.getLogger(__name__).warning(
            "Failed to persist reconcile result for %s: %s",
            getattr(record, "symbol", "?"),
            exc_info=True,
        )
