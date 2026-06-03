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

from fincouncil.data.adapters.yfinance import YFinanceAdapter
from fincouncil.data.cache.manager import CacheManager
from fincouncil.data.mcp.tools import DataNotAvailableError, InvalidParameterError, get_fundamentals as mcp_get_fundamentals, get_price
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

    Fetches fundamentals via FinCouncil MCP tool and formats as CSV.

    Args:
        ticker: Ticker symbol
        curr_date: Current date (optional)

    Returns:
        String with fundamental data in TradingAgents format
    """
    canonical = _normalize_to_canonical(ticker)
    currency = _detect_currency(canonical)

    # Fetch from FinCouncil data layer
    try:
        records = mcp_get_fundamentals(symbol=canonical, period="FY")
    except (DataNotAvailableError, InvalidParameterError, Exception):
        return _format_no_data(ticker, canonical)

    if not records:
        return _format_no_data(ticker, canonical)

    return _format_fundamentals_csv(records, ticker, canonical, currency)


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    """Get balance sheet data.

    Fetches balance sheet via YFinanceAdapter and formats as CSV.

    Args:
        ticker: Ticker symbol
        freq: Frequency (annual or quarterly)
        curr_date: Current date (optional)

    Returns:
        String with balance sheet data or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    currency = _detect_currency(canonical)

    # Fetch from YFinanceAdapter (filter for balance_sheet endpoint)
    try:
        adapter = YFinanceAdapter()
        all_records = adapter.get_fundamentals(symbol=canonical, period="FY")
        # Filter for balance_sheet endpoint only
        records = [r for r in all_records if r.get("endpoint") == "balance_sheet"]
    except Exception:
        return _format_no_data(ticker, canonical)

    if not records:
        return _format_no_data(ticker, canonical)

    return _format_statement_csv(records, ticker, canonical, currency, "Balance Sheet", freq)


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    """Get cash flow data.

    Fetches cash flow via YFinanceAdapter and formats as CSV.

    Args:
        ticker: Ticker symbol
        freq: Frequency (annual or quarterly)
        curr_date: Current date (optional)

    Returns:
        String with cash flow data or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    currency = _detect_currency(canonical)

    # Fetch from YFinanceAdapter (filter for cashflow endpoint)
    try:
        adapter = YFinanceAdapter()
        all_records = adapter.get_fundamentals(symbol=canonical, period="FY")
        # Filter for cashflow endpoint only
        records = [r for r in all_records if r.get("endpoint") == "cashflow"]
    except Exception:
        return _format_no_data(ticker, canonical)

    if not records:
        return _format_no_data(ticker, canonical)

    return _format_statement_csv(records, ticker, canonical, currency, "Cash Flow", freq)


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
) -> str:
    """Get income statement data.

    Fetches income statement via YFinanceAdapter and formats as CSV.

    Args:
        ticker: Ticker symbol
        freq: Frequency (annual or quarterly)
        curr_date: Current date (optional)

    Returns:
        String with income statement data or placeholder
    """
    canonical = _normalize_to_canonical(ticker)
    currency = _detect_currency(canonical)

    # Fetch from YFinanceAdapter (filter for financials endpoint)
    try:
        adapter = YFinanceAdapter()
        all_records = adapter.get_fundamentals(symbol=canonical, period="FY")
        # Filter for financials endpoint only
        records = [r for r in all_records if r.get("endpoint") == "financials"]
    except Exception:
        return _format_no_data(ticker, canonical)

    if not records:
        return _format_no_data(ticker, canonical)

    return _format_statement_csv(records, ticker, canonical, currency, "Income Statement", freq)


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


def _format_fundamentals_csv(
    records: list[dict[str, any]],
    original_symbol: str,
    canonical: str,
    currency: str,
) -> str:
    """Format fundamentals records to TradingAgents CSV format.

    Args:
        records: List of fundamentals record dicts
        original_symbol: Original symbol requested
        canonical: Canonical symbol resolved
        currency: ISO currency code

    Returns:
        CSV string with header in TradingAgents format
    """
    if not records:
        return _format_no_data(original_symbol, canonical)

    # Build CSV
    output = StringIO()
    output.write(f"# Company Fundamentals for {original_symbol}\n")
    output.write(f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"# Total records: {len(records)}\n")
    output.write(f"# Source: {records[0].get('source', 'yfinance:yfinance')}\n")
    output.write(f"# Currency: {currency}\n")
    output.write(f"# Exchange: {_extract_exchange(canonical)}\n\n")

    # Process records - separate info (metrics) from statement records
    info_records = [r for r in records if r.get("endpoint") == "info"]
    statement_records = [r for r in records if r.get("endpoint") != "info"]

    # Output info metrics first if available
    if info_records:
        info = info_records[0]
        output.write("# Key Metrics\n")
        # Output selected key metrics
        key_fields = [
            "marketCap", "forwardPE", "trailingPE", "dividendYield",
            "beta", "sharesOutstanding", "bookValue", "profitMargins",
            "enterpriseToEbitda", "52WeekChange", "sector", "industry"
        ]
        for field in key_fields:
            if field in info:
                output.write(f"{field}: {_decimal_to_str(info[field])}\n")
        output.write("\n")

    # Output statement records summary
    if statement_records:
        output.write(f"# Financial Statements Available: {len(statement_records)} records\n")
        for record in statement_records[:5]:  # Show first 5
            endpoint = record.get("endpoint", "unknown")
            period = record.get("period", "N/A")
            output.write(f"#   - {endpoint}: {period}\n")
        if len(statement_records) > 5:
            output.write(f"#   ... and {len(statement_records) - 5} more\n")

    return output.getvalue()


def _format_statement_csv(
    records: list[dict[str, any]],
    original_symbol: str,
    canonical: str,
    currency: str,
    statement_type: str,
    freq: str,
) -> str:
    """Format financial statement records to TradingAgents CSV format.

    Args:
        records: List of statement record dicts (filtered by endpoint)
        original_symbol: Original symbol requested
        canonical: Canonical symbol resolved
        currency: ISO currency code
        statement_type: Type of statement (e.g., "Balance Sheet", "Cash Flow")
        freq: Frequency (annual or quarterly)

    Returns:
        CSV string with header in TradingAgents format
    """
    if not records:
        return _format_no_data(original_symbol, canonical)

    # Build CSV
    output = StringIO()
    output.write(f"# {statement_type} data for {original_symbol} ({freq})\n")
    output.write(f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"# Total records: {len(records)}\n")
    output.write(f"# Source: {records[0].get('source', 'yfinance:yfinance')}\n")
    output.write(f"# Currency: {currency}\n")
    output.write(f"# Exchange: {_extract_exchange(canonical)}\n\n")

    # Collect all unique field names across all records
    all_fields = set()
    for record in records:
        # Skip metadata fields
        for key in record.keys():
            if key not in {"endpoint", "symbol", "period", "source", "provider",
                          "provider_backend", "provider_symbol", "provider_call"}:
                all_fields.add(key)

    # Sort fields for consistent output
    sorted_fields = sorted(all_fields)

    # Write CSV header
    output.write(f"Period,{','.join(sorted_fields)}\n")

    # Write data rows - sort by period (most recent first)
    sorted_records = sorted(records, key=lambda r: str(r.get("period", "")), reverse=True)
    for record in sorted_records:
        period = record.get("period", "N/A")
        row_values = []
        for field in sorted_fields:
            val = record.get(field)
            row_values.append(_decimal_to_str(val))
        output.write(f"{period},{','.join(row_values)}\n")

    return output.getvalue()
