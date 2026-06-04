"""MCP server entry point for FinCouncil data layer.

This module provides a simple server that exposes FinCouncil data tools
via the Model Context Protocol (MCP). It can be started as an MCP server
for consumption by AI agents.

The server initializes a DuckDB warehouse and cache manager on startup,
then exposes tool functions for:
- get_price: EOD price data
- get_fundamentals: Fundamental data
- list_symbols: Symbol listing
- reconcile: Cross-source verification
- get_news/get_sentiment/get_macro: news, sentiment, and macro observations
"""

from __future__ import annotations

from pathlib import Path

from fincouncil.data.cache.manager import CacheManager
from fincouncil.data.mcp.tools import (
    get_fundamentals,
    get_macro,
    get_news,
    get_price,
    get_sentiment,
    list_symbols,
    reconcile,
)
from fincouncil.data.store.warehouse import DuckDBWarehouse


class FinCouncilMCPServer:
    """FinCouncil MCP server for data layer access.

    This server provides access to the FinCouncil data pipeline through
    MCP-compatible tool functions. It manages warehouse and cache lifecycle.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Initialize the MCP server with warehouse and cache.

        Args:
            db_path: Path to DuckDB database file. Use ":memory:" for in-memory.
        """
        self._warehouse = DuckDBWarehouse(str(db_path))
        self._cache = CacheManager(self._warehouse)

    def get_price(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        *,
        source: str | None = None,
        currency: str = "USD",
    ) -> list[dict]:
        """Get EOD price data for a symbol.

        Args:
            symbol: Canonical symbol (e.g., "US:AAPL", "SET:PTT").
            start_date: ISO date string (inclusive).
            end_date: ISO date string (inclusive).
            source: Optional data source filter.
            currency: ISO currency code (default: "USD").

        Returns:
            List of PriceRecord dicts.
        """
        return get_price(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            cache_manager=self._cache,
            source=source,
            currency=currency,
        )

    def get_fundamentals(
        self,
        symbol: str,
        period: str = "FY",
    ) -> list[dict]:
        """Get fundamental data for a symbol.

        Args:
            symbol: Canonical symbol (e.g., "US:AAPL").
            period: Financial statement period ("FY" or "Q").

        Returns:
            List of FundamentalsRecord dicts.
        """
        return get_fundamentals(symbol=symbol, period=period)

    def get_news(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        """Get company news for a symbol."""
        return get_news(symbol=symbol, start_date=start_date, end_date=end_date)

    def get_sentiment(self, symbol: str) -> list[dict]:
        """Get sentiment for a symbol."""
        return get_sentiment(symbol=symbol)

    def get_macro(self, series_id: str, **kwargs) -> list[dict]:
        """Get macro observations for a FRED series."""
        return get_macro(series_id=series_id, **kwargs)

    def list_symbols(self, exchange: str = "US") -> list[dict]:
        """List supported symbols for an exchange.

        Args:
            exchange: Exchange code (e.g., "US", "SET", "TSE").

        Returns:
            List of symbol metadata dicts.
        """
        return list_symbols(exchange=exchange)

    def reconcile(
        self,
        symbol: str,
        field: str,
        trade_date: str,
    ) -> dict:
        """Reconcile a data field across multiple sources.

        Args:
            symbol: Canonical symbol (e.g., "US:AAPL").
            field: Field to reconcile (e.g., "close", "high").
            trade_date: ISO date string.

        Returns:
            ReconcileLogRecord dict.
        """
        return reconcile(
            symbol=symbol,
            field=field,
            trade_date=trade_date,
            cache_manager=self._cache,
        )


def create_server(db_path: str | Path = ":memory:") -> FinCouncilMCPServer:
    """Create a new FinCouncil MCP server instance.

    Args:
        db_path: Path to DuckDB database file. Use ":memory:" for in-memory.

    Returns:
        Configured FinCouncilMCPServer instance.
    """
    return FinCouncilMCPServer(db_path=db_path)


# For standalone execution
if __name__ == "__main__":
    import sys

    db_path_arg = sys.argv[1] if len(sys.argv) > 1 else ":memory:"
    server = create_server(db_path=db_path_arg)
    print(f"FinCouncil MCP Server initialized with db_path: {db_path_arg}")
    print("Available tools: get_price, get_fundamentals, get_news, get_sentiment, get_macro, list_symbols, reconcile")
