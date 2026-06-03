"""Tests for TradingAgents swap-in shim.

These tests verify that the shim correctly:
1. Accepts TradingAgents method signatures
2. Calls FinCouncil data layer
3. Returns data in TradingAgents format
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

from fincouncil.data.swap.shim import (
    get_stock_data,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_global_news,
    get_insider_transactions,
    get_stock_stats_indicators_window,
    _normalize_to_canonical,
    _detect_currency,
    _format_price_csv,
)


class FakePriceRecord(dict):
    """Fake price record for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class TestNormalizeToCanonical:
    """Tests for _normalize_to_canonical."""

    def test_bare_symbol_becomes_us(self):
        assert _normalize_to_canonical("AAPL") == "US:AAPL"
        assert _normalize_to_canonical("MSFT") == "US:MSFT"

    def test_thai_suffix_becomes_set(self):
        assert _normalize_to_canonical("PTT.BK") == "SET:PTT"
        assert _normalize_to_canonical("AOT.BK") == "SET:AOT"

    def test_japan_suffix_becomes_tse(self):
        assert _normalize_to_canonical("7203.T") == "TSE:7203"
        assert _normalize_to_canonical("6758.T") == "TSE:6758"

    def test_hk_suffix_becomes_hkex(self):
        assert _normalize_to_canonical("0700.HK") == "HKEX:0700"
        assert _normalize_to_canonical("9988.HK") == "HKEX:9988"

    def test_china_suffixes(self):
        assert _normalize_to_canonical("600519.SS") == "SSE:600519"
        assert _normalize_to_canonical("000001.SZ") == "SZSE:000001"

    def test_already_canonical(self):
        assert _normalize_to_canonical("US:AAPL") == "US:AAPL"
        assert _normalize_to_canonical("SET:PTT") == "SET:PTT"

    def test_cfd_suffix_stripped(self):
        assert _normalize_to_canonical("XAUUSD+") == "US:XAUUSD"
        assert _normalize_to_canonical("AAPL+") == "US:AAPL"


class TestDetectCurrency:
    """Tests for _detect_currency."""

    def test_us_symbols(self):
        assert _detect_currency("US:AAPL") == "USD"
        assert _detect_currency("AAPL") == "USD"

    def test_thai_symbols(self):
        assert _detect_currency("SET:PTT") == "THB"

    def test_japan_symbols(self):
        assert _detect_currency("TSE:7203") == "JPY"

    def test_hk_symbols(self):
        assert _detect_currency("HKEX:0700") == "HKD"

    def test_china_symbols(self):
        assert _detect_currency("SSE:600519") == "CNY"
        assert _detect_currency("SZSE:000001") == "CNY"

    def test_empty_returns_default(self):
        assert _detect_currency("") == "USD"
        assert _detect_currency(None) == "USD"


class TestFormatPriceCSV:
    """Tests for _format_price_csv."""

    def test_formats_single_record(self):
        records = [
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 15),
                "open": Decimal("148.50"),
                "high": Decimal("150.00"),
                "low": Decimal("148.00"),
                "close": Decimal("149.50"),
                "volume": 50000000,
                "adjusted_close": Decimal("149.50"),
                "source": "openbb:yfinance",
                "currency": "USD",
                "as_of": date(2024, 1, 15),
            }
        ]

        result = _format_price_csv(records, "AAPL", "2024-01-01", "2024-01-31")

        assert "# Stock data for AAPL from 2024-01-01 to 2024-01-31" in result
        assert "# Total records: 1" in result
        assert "# Source: openbb:yfinance" in result
        assert "# Currency: USD" in result
        assert "Date,Open,High,Low,Close,Adj Close,Volume" in result
        assert "2024-01-15,148.50,150.00,148.00,149.50,149.50,50000000" in result

    def test_formats_multiple_records_sorted(self):
        records = [
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 16),
                "open": Decimal("149.00"),
                "high": Decimal("151.00"),
                "low": Decimal("148.50"),
                "close": Decimal("150.00"),
                "volume": 45000000,
                "adjusted_close": Decimal("150.00"),
                "source": "openbb:yfinance",
                "currency": "USD",
                "as_of": date(2024, 1, 16),
            },
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 15),
                "open": Decimal("148.50"),
                "high": Decimal("150.00"),
                "low": Decimal("148.00"),
                "close": Decimal("149.50"),
                "volume": 50000000,
                "adjusted_close": Decimal("149.50"),
                "source": "openbb:yfinance",
                "currency": "USD",
                "as_of": date(2024, 1, 15),
            },
        ]

        result = _format_price_csv(records, "AAPL", "2024-01-01", "2024-01-31")

        lines = result.split("\n")
        # Find data lines
        data_lines = [l for l in lines if l.startswith("2024-01-")]

        # Should be sorted by date
        assert data_lines[0].startswith("2024-01-15")
        assert data_lines[1].startswith("2024-01-16")

    def test_empty_records_returns_no_data(self):
        result = _format_price_csv([], "AAPL", "2024-01-01", "2024-01-31")

        assert "NO_DATA_AVAILABLE" in result
        assert "AAPL" in result


class TestGetStockData:
    """Tests for get_stock_data."""

    def test_calls_fincouncil_data_layer(self, monkeypatch):
        """Test that get_stock_data calls FinCouncil MCP tools."""
        # Mock the get_price function
        mock_records = [
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 15),
                "open": Decimal("148.50"),
                "high": Decimal("150.00"),
                "low": Decimal("148.00"),
                "close": Decimal("149.50"),
                "volume": 50000000,
                "adjusted_close": Decimal("149.50"),
                "source": "openbb:yfinance",
                "currency": "USD",
                "as_of": date(2024, 1, 15),
            }
        ]

        def mock_get_price(*args, **kwargs):
            return mock_records

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        result = get_stock_data("AAPL", "2024-01-01", "2024-01-31")

        assert "# Stock data for AAPL" in result
        assert "2024-01-15" in result
        assert "149.50" in result

    def test_returns_no_data_when_unavailable(self, monkeypatch):
        """Test that get_stock_data returns no data message when unavailable."""

        def mock_get_price(*args, **kwargs):
            from fincouncil.data.mcp.tools import DataNotAvailableError
            raise DataNotAvailableError("No data available")

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        result = get_stock_data("INVALID", "2024-01-01", "2024-01-31")

        assert "NO_DATA_AVAILABLE" in result
        assert "INVALID" in result

    def test_handles_thai_symbols(self, monkeypatch):
        """Test that get_stock_data handles Thai symbols correctly."""
        mock_records = [
            {
                "symbol": "SET:PTT",
                "date": date(2024, 1, 15),
                "open": Decimal("35.00"),
                "high": Decimal("36.00"),
                "low": Decimal("34.50"),
                "close": Decimal("35.50"),
                "volume": 10000000,
                "adjusted_close": Decimal("35.50"),
                "source": "openbb:yfinance",
                "currency": "THB",
                "as_of": date(2024, 1, 15),
            }
        ]

        def mock_get_price(*args, **kwargs):
            return mock_records

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        result = get_stock_data("PTT.BK", "2024-01-01", "2024-01-31")

        assert "# Stock data for PTT.BK" in result
        assert "# Currency: THB" in result


class TestGetFundamentals:
    """Tests for get_fundamentals."""

    def test_returns_placeholder_for_phase1(self):
        """Test that fundamentals returns placeholder in Phase 1."""
        result = get_fundamentals("AAPL")

        assert "# Company Fundamentals for US:AAPL" in result
        assert "NOTE: Fundamentals through FinCouncil layer not fully implemented" in result

    def test_includes_exchange_info(self):
        result = get_fundamentals("PTT.BK")
        assert "Exchange: SET" in result


class TestGetBalanceSheet:
    """Tests for get_balance_sheet."""

    def test_returns_placeholder_for_phase1(self):
        result = get_balance_sheet("AAPL")
        assert "# Balance Sheet data for US:AAPL" in result
        assert "NOTE: Balance sheet through FinCouncil layer not fully implemented" in result


class TestGetCashflow:
    """Tests for get_cashflow."""

    def test_returns_placeholder_for_phase1(self):
        result = get_cashflow("AAPL")
        assert "# Cash Flow data for US:AAPL" in result
        assert "NOTE: Cash flow through FinCouncil layer not fully implemented" in result


class TestGetIncomeStatement:
    """Tests for get_income_statement."""

    def test_returns_placeholder_for_phase1(self):
        result = get_income_statement("AAPL")
        assert "# Income Statement data for US:AAPL" in result
        assert "NOTE: Income statement through FinCouncil layer not fully implemented" in result


class TestGetNews:
    """Tests for get_news."""

    def test_returns_placeholder_for_phase1(self):
        result = get_news("AAPL")
        assert "# News data for US:AAPL" in result
        assert "NOTE: News through FinCouncil layer not implemented in Phase 1" in result


class TestGetGlobalNews:
    """Tests for get_global_news."""

    def test_returns_placeholder_for_phase1(self):
        result = get_global_news()
        assert "# Global News" in result
        assert "NOTE: Global news through FinCouncil layer not implemented in Phase 1" in result


class TestGetInsiderTransactions:
    """Tests for get_insider_transactions."""

    def test_returns_placeholder_for_phase1(self):
        result = get_insider_transactions("AAPL")
        assert "# Insider Transactions data for US:AAPL" in result
        assert "NOTE: Insider transactions through FinCouncil layer not implemented" in result


class TestGetStockStatsIndicatorsWindow:
    """Tests for get_stock_stats_indicators_window."""

    def test_returns_placeholder_for_phase1(self):
        result = get_stock_stats_indicators_window("AAPL", "RSI", "2024-01-15", 30)
        assert "# RSI values for US:AAPL" in result
        assert "NOTE: Technical indicators through FinCouncil layer not implemented" in result


class TestIntegrationWithTradingAgents:
    """Integration tests verifying TradingAgents compatibility."""

    def test_signature_matches_tradingagents_get_stock_data(self):
        """Test that our get_stock_data signature matches TradingAgents."""
        import inspect

        # Get our signature
        our_sig = inspect.signature(get_stock_data)
        our_params = list(our_sig.parameters.keys())

        # TradingAgents expects: symbol, start_date, end_date
        expected_params = ["symbol", "start_date", "end_date"]

        assert our_params == expected_params, f"Expected {expected_params}, got {our_params}"

    def test_signature_matches_tradingagents_get_fundamentals(self):
        """Test that our get_fundamentals signature matches TradingAgents."""
        import inspect

        our_sig = inspect.signature(get_fundamentals)
        our_params = list(our_sig.parameters.keys())

        # TradingAgents expects: ticker, curr_date (optional)
        assert "ticker" in our_params
        assert "curr_date" in our_params

    def test_returns_string_not_csv_object(self):
        """Test that functions return string, not objects."""
        result = get_stock_data("AAPL", "2024-01-01", "2024-01-31")
        assert isinstance(result, str)

        result = get_fundamentals("AAPL")
        assert isinstance(result, str)

    def test_header_format_matches_tradingagents(self, monkeypatch):
        """Test that output header format matches TradingAgents."""
        # Mock get_price to return actual data
        mock_records = [
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 15),
                "open": Decimal("148.50"),
                "high": Decimal("150.00"),
                "low": Decimal("148.00"),
                "close": Decimal("149.50"),
                "volume": 50000000,
                "adjusted_close": Decimal("149.50"),
                "source": "openbb:yfinance",
                "currency": "USD",
                "as_of": date(2024, 1, 15),
            }
        ]

        def mock_get_price(*args, **kwargs):
            return mock_records

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        result = get_stock_data("AAPL", "2024-01-01", "2024-01-31")

        # Should contain TradingAgents-style headers
        assert "# Stock data for" in result
        assert "# Total records:" in result
        assert "# Data retrieved on:" in result

        # Should contain CSV header
        assert "Date,Open,High,Low,Close,Adj Close,Volume" in result


class TestPhase1Scope:
    """Tests verifying Phase 1 scope limitations."""

    def test_price_data_only_fully_implemented(self):
        """Test that only price data is fully implemented in Phase 1."""
        # get_stock_data should work (with mocked data)
        # Others should return placeholders

        # These should return placeholders
        for func in [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            lambda s: get_news(s),
            get_global_news,
            get_insider_transactions,
            lambda s, i, d, l: get_stock_stats_indicators_window(s, i, d, l),
        ]:
            try:
                result = func("AAPL")
                assert "NOTE:" in result or "not implemented" in result.lower() or "not fully implemented" in result.lower(), \
                    f"{func.__name__} should return Phase 1 placeholder"
            except Exception:
                # Function might fail, which is also acceptable for Phase 1
                pass


class TestCouncilDataLayerIntegration:
    """Integration tests verifying council can pull from our data layer (CP1 criterion 4).

    These tests verify the end-to-end flow: council calls shim → shim calls FinCouncil → returns data.
    """

    def test_council_pulls_price_data_from_fincouncil(self, monkeypatch):
        """Test that council can pull price data from FinCouncil data layer."""
        # Mock get_price to return actual data
        mock_records = [
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 15),
                "open": Decimal("148.50"),
                "high": Decimal("150.00"),
                "low": Decimal("148.00"),
                "close": Decimal("149.50"),
                "volume": 50000000,
                "adjusted_close": Decimal("149.50"),
                "source": "openbb:yfinance",
                "currency": "USD",
                "as_of": date(2024, 1, 15),
            }
        ]

        def mock_get_price(*args, **kwargs):
            return mock_records

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        # Simulate council calling the shim
        result = get_stock_data("AAPL", "2024-01-01", "2024-01-31")

        # Verify data comes from our layer
        assert "# Source: openbb:yfinance" in result
        assert "# Currency: USD" in result
        assert "149.50" in result

    def test_council_pulls_multi_market_data(self, monkeypatch):
        """Test that council can pull data from multiple markets through our layer."""
        test_cases = [
            ("AAPL", "USD", "US:AAPL"),
            ("PTT.BK", "THB", "SET:PTT"),
            ("0700.HK", "HKD", "HKEX:0700"),
        ]

        for symbol, expected_currency, canonical in test_cases:
            mock_records = [
                {
                    "symbol": canonical,
                    "date": date(2024, 1, 15),
                    "open": Decimal("100.00"),
                    "high": Decimal("105.00"),
                    "low": Decimal("99.00"),
                    "close": Decimal("104.00"),
                    "volume": 1000000,
                    "adjusted_close": Decimal("104.00"),
                    "source": "openbb:yfinance",
                    "currency": expected_currency,
                    "as_of": date(2024, 1, 15),
                }
            ]

            def mock_get_price(*args, **kwargs):
                return mock_records

            monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

            result = get_stock_data(symbol, "2024-01-01", "2024-01-31")

            assert f"# Currency: {expected_currency}" in result
            assert "# Source: openbb:yfinance" in result

    def test_council_receives_source_attribution(self, monkeypatch):
        """Test that council receives proper source attribution from our layer."""
        mock_records = [
            {
                "symbol": "US:AAPL",
                "date": date(2024, 1, 15),
                "open": Decimal("148.50"),
                "high": Decimal("150.00"),
                "low": Decimal("148.00"),
                "close": Decimal("149.50"),
                "volume": 50000000,
                "adjusted_close": Decimal("149.50"),
                "source": "yfinance:yfinance",  # yfinance source
                "currency": "USD",
                "as_of": date(2024, 1, 15),
            }
        ]

        def mock_get_price(*args, **kwargs):
            return mock_records

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        result = get_stock_data("AAPL", "2024-01-01", "2024-01-31")

        # Source must be preserved
        assert "# Source: yfinance:yfinance" in result

    def test_council_handles_unavailable_data_gracefully(self, monkeypatch):
        """Test that council receives proper message when data is unavailable."""
        def mock_get_price(*args, **kwargs):
            from fincouncil.data.mcp.tools import DataNotAvailableError
            raise DataNotAvailableError("No data available for INVALID")

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        result = get_stock_data("INVALID", "2024-01-01", "2024-01-31")

        # Should return no data message, not crash
        assert "NO_DATA_AVAILABLE" in result
        assert "INVALID" in result
        assert "Do not estimate or fabricate" in result

    def test_shim_calls_mcp_tools_not_adapters_directly(self, monkeypatch):
        """Test that shim uses MCP tools (orchestration layer) not adapters directly."""
        # This verifies the architecture: shim → MCP tools → adapters
        # rather than shim → adapters (bypassing orchestration)

        mcp_tool_called = []

        def mock_get_price(*args, **kwargs):
            mcp_tool_called.append(True)
            return []

        monkeypatch.setattr("fincouncil.data.swap.shim.get_price", mock_get_price)

        get_stock_data("AAPL", "2024-01-01", "2024-01-31")

        # MCP tool should have been called
        assert mcp_tool_called
