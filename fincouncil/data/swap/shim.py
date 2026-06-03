"""TradingAgents swap-in shim implementation.

This module provides vendor-compatible implementations of TradingAgents
data methods that redirect to the FinCouncil data layer.

Each function matches the TradingAgents method signature and returns
data in the expected CSV+header string format.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Annotated

from fincouncil.data.cache.manager import CacheManager
from fincouncil.data.mcp.tools import DataNotAvailableError, InvalidParameterError, get_price
from fincouncil.data.schema import CurrencyCode
from fincouncil.data.store.warehouse import DuckDBWarehouse


def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Get OHLCV stock data for a symbol.

    Redirects to FinCouncil MCP get_price tool and converts to
    TradingAgents CSV+header format.

    Args:
        symbol: Ticker symbol (can be canonical or broker format)
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string with header metadata in TradingAgents format
    """
    # Convert broker symbol to canonical if needed
    canonical = _normalize_to_canonical(symbol)

    # Determine currency from symbol
    currency = _detect_currency(canonical)

    # Setup cache and warehouse
    warehouse = DuckDBWarehouse(":memory:")
    cache = CacheManager(warehouse)

    # Fetch from FinCouncil data layer
    try:
        records = get_price(
            symbol=canonical,
            start_date=start_date,
            end_date=end_date,
            cache_manager=cache,
            currency=currency,
        )
    except (DataNotAvailableError, InvalidParameterError):
        # Return TradingAgents-style no data message
        return _format_no_data(symbol, canonical)

    if not records:
        return _format_no_data(symbol, canonical)

    # Convert to CSV format
    return _format_price_csv(records, symbol, start_date, end_date)


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for FinCouncil)"] = None,
) -> str:
    """Get company fundamentals overview.

    Phase 1 note: Fundamentals through FinCouncil layer is limited.
    This is a placeholder that returns available fields.

    Args:
        ticker: Ticker symbol
        curr_date: Current date (optional)

    Returns:
        String with fundamental data in TradingAgents format
    """
    canonical = _normalize_to_canonical(ticker)

    # Phase 1: Return a placeholder indicating fundamentals not fully available
    # In future phases, this would call MCP get_fundamentals
    return f"# Company Fundamentals for {canonical}\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Fundamentals through FinCouncil layer not fully implemented in Phase 1.\n" \
           f"# Please use yfinance or alpha_vantage vendor for fundamentals.\n" \
           f"#\n" \
           f"Name: {canonical}\n" \
           f"Exchange: {_extract_exchange(canonical)}\n"


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    """Get balance sheet data.

    Phase 1: Returns placeholder indicating limited availability.

    Args:
        ticker: Ticker symbol
        freq: Frequency (annual or quarterly)
        curr_date: Current date (optional)

    Returns:
        String with balance sheet data or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    return f"# Balance Sheet data for {canonical} ({freq})\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Balance sheet through FinCouncil layer not fully implemented in Phase 1.\n" \
           f"# Please use yfinance or alpha_vantage vendor for balance sheet data.\n"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    """Get cash flow data.

    Phase 1: Returns placeholder indicating limited availability.

    Args:
        ticker: Ticker symbol
        freq: Frequency (annual or quarterly)
        curr_date: Current date (optional)

    Returns:
        String with cash flow data or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    return f"# Cash Flow data for {canonical} ({freq})\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Cash flow through FinCouncil layer not fully implemented in Phase 1.\n" \
           f"# Please use yfinance or alpha_vantage vendor for cash flow data.\n"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    """Get income statement data.

    Phase 1: Returns placeholder indicating limited availability.

    Args:
        ticker: Ticker symbol
        freq: Frequency (annual or quarterly)
        curr_date: Current date (optional)

    Returns:
        String with income statement data or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    return f"# Income Statement data for {canonical} ({freq})\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Income statement through FinCouncil layer not fully implemented in Phase 1.\n" \
           f"# Please use yfinance or alpha_vantage vendor for income statement data.\n"


def get_news(
    symbol: Annotated[str, "ticker symbol of the company"],
) -> str:
    """Get news data for a symbol.

    Phase 1: Returns placeholder indicating news not available.

    Args:
        symbol: Ticker symbol

    Returns:
        String with news data or placeholder
    """
    canonical = _normalize_to_canonical(symbol)
    return f"# News data for {canonical}\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: News through FinCouncil layer not implemented in Phase 1.\n" \
           f"# Please use yfinance vendor for news data.\n"


def get_global_news() -> str:
    """Get global macro news.

    Phase 1: Returns placeholder indicating news not available.

    Returns:
        String with global news or placeholder
    """
    return f"# Global News\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Global news through FinCouncil layer not implemented in Phase 1.\n" \
           f"# Please use yfinance vendor for global news.\n"


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"],
) -> str:
    """Get insider transactions data.

    Phase 1: Returns placeholder indicating insider data not available.

    Args:
        ticker: Ticker symbol

    Returns:
        String with insider transactions or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    return f"# Insider Transactions data for {canonical}\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Insider transactions through FinCouncil layer not implemented in Phase 1.\n" \
           f"# Please use yfinance vendor for insider transactions.\n"


def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """Get technical indicator values.

    Phase 1: Returns placeholder indicating indicators not calculated.

    Args:
        symbol: Ticker symbol
        indicator: Technical indicator name
        curr_date: Current trading date
        look_back_days: Days to look back

    Returns:
        String with indicator values or placeholder
    """
    canonical = _normalize_to_canonical(symbol)
    return f"# {indicator} values for {canonical}\n" \
           f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
           f"#\n" \
           f"# NOTE: Technical indicators through FinCouncil layer not implemented in Phase 1.\n" \
           f"# Please use yfinance vendor for technical indicators.\n"


# Helper functions

def _normalize_to_canonical(symbol: str) -> str:
    """Convert broker symbol to FinCouncil canonical format.

    Args:
        symbol: Broker symbol (e.g., "AAPL", "PTT.BK", "XAUUSD+")

    Returns:
        Canonical symbol (e.g., "US:AAPL", "SET:PTT", "US:XAUUSD")
    """
    if not symbol:
        return symbol

    s = symbol.strip().upper()

    # Already canonical format
    if ":" in s:
        return s

    # Strip broker CFD suffix
    s = s.rstrip("+")

    # Map common suffixes to exchanges
    suffix_map = {
        ".BK": ("SET", "BK"),
        ".T": ("TSE", "T"),
        ".HK": ("HKEX", "HK"),
        ".SS": ("SSE", "SS"),
        ".SZ": ("SZSE", "SZ"),
    }

    for suffix, (exchange, code) in suffix_map.items():
        if s.endswith(suffix):
            ticker = s[: -len(suffix)]
            return f"{exchange}:{ticker}"

    # Default to US
    return f"US:{s}"


def _detect_currency(symbol: str) -> str:
    """Detect currency from canonical symbol.

    Args:
        symbol: Canonical symbol (e.g., "US:AAPL", "SET:PTT")

    Returns:
        ISO currency code
    """
    if not symbol or ":" not in symbol:
        return "USD"

    exchange = symbol.split(":")[0]

    currency_map = {
        "US": "USD",
        "SET": "THB",
        "TSE": "JPY",
        "HKEX": "HKD",
        "SSE": "CNY",
        "SZSE": "CNY",
    }

    return currency_map.get(exchange, "USD")


def _extract_exchange(symbol: str) -> str:
    """Extract exchange code from canonical symbol."""
    if ":" in symbol:
        return symbol.split(":")[0]
    return "US"


def _format_price_csv(
    records: list[dict[str, any]],
    original_symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """Format price records to TradingAgents CSV format.

    Args:
        records: List of price record dicts
        original_symbol: Original symbol requested
        start_date: Start date
        end_date: End date

    Returns:
        CSV string with header in TradingAgents format
    """
    if not records:
        return _format_no_data(original_symbol, original_symbol)

    # Sort by date
    sorted_records = sorted(records, key=lambda r: r.get("date", ""))

    # Build CSV
    output = StringIO()
    output.write(f"# Stock data for {original_symbol} from {start_date} to {end_date}\n")
    output.write(f"# Total records: {len(sorted_records)}\n")
    output.write(f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"# Source: {records[0].get('source', 'fincouncil')}\n")
    output.write(f"# Currency: {records[0].get('currency', 'USD')}\n\n")

    # CSV header
    output.write("Date,Open,High,Low,Close,Adj Close,Volume\n")

    # Data rows
    for record in sorted_records:
        record_date = record.get("date", "")
        if isinstance(record_date, date):
            record_date = record_date.isoformat()

        output.write(
            f"{record_date},"
            f"{_decimal_to_str(record.get('open'))},"
            f"{_decimal_to_str(record.get('high'))},"
            f"{_decimal_to_str(record.get('low'))},"
            f"{_decimal_to_str(record.get('close'))},"
            f"{_decimal_to_str(record.get('adjusted_close'))},"
            f"{record.get('volume', 0)}\n"
        )

    return output.getvalue()


def _decimal_to_str(value: any) -> str:
    """Convert Decimal or numeric value to string for CSV.

    Args:
        value: Decimal or numeric value

    Returns:
        String value rounded to 2 decimal places
    """
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{float(value):.2f}"
    return str(value)


def _format_no_data(original_symbol: str, canonical: str) -> str:
    """Format TradingAgents-style no data message.

    Args:
        original_symbol: Original symbol requested
        canonical: Canonical symbol resolved

    Returns:
        No data message string
    """
    if canonical == original_symbol:
        resolved = ""
    else:
        resolved = f" (resolved to '{canonical}')"

    return (
        f"NO_DATA_AVAILABLE: No market data found for '{original_symbol}'{resolved} from "
        f"FinCouncil data layer. The symbol may be invalid, delisted, or not covered. "
        f"Do not estimate or fabricate values — report that data is unavailable for this symbol."
    )
