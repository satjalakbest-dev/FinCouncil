"""Tests for MCP tool functions."""

from datetime import date
from unittest.mock import MagicMock, Mock
from decimal import Decimal

import pytest

from fincouncil.data.mcp.tools import (
    DataNotAvailableError,
    InvalidParameterError,
    MCPToolError,
    get_fundamentals,
    get_price,
    list_symbols,
    reconcile,
    _validate_dates,
    _validate_symbol,
    _validate_period,
    _validate_exchange,
    _validate_trade_date,
    _validate_price_field,
)
from fincouncil.data.schema import PriceRecord, CurrencyCode, ReconcileLogRecord, ReconcileStatus


class FakeWarehouse:
    """Fake warehouse for testing."""

    def __init__(self):
        self.records = []

    def upsert_prices(self, rows):
        self.records.extend(rows)
        return len(rows)

    def query_prices(self, symbol, start_date, end_date, source=None):
        import pandas as pd

        if not self.records:
            return pd.DataFrame()

        df_data = [r for r in self.records if r["symbol"] == symbol]
        return pd.DataFrame(df_data)


class FakeCacheManager:
    """Fake cache manager for testing."""

    def __init__(self, warehouse=None):
        self.warehouse = warehouse or FakeWarehouse()
        self.fetch_called = False

    def get_or_fetch(self, symbol, start_date, end_date, adapter, currency, source, force_refresh=False):
        self.fetch_called = True
        # Return fake price records
        return [
            PriceRecord(
                kind="price",
                symbol=symbol,
                date=start_date,
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("99.0"),
                close=Decimal("104.0"),
                volume=1000000,
                adjusted_close=Decimal("104.0"),
                source=source,
                currency=CurrencyCode(currency),
                as_of=date.today(),
            )
        ]

    def is_fresh(self, symbol, start_date, end_date, source):
        return False


class TestValidateDates:
    """Tests for _validate_dates."""

    def test_valid_dates(self):
        _validate_dates("2024-01-01", "2024-01-31")

    def test_start_after_end_raises(self):
        with pytest.raises(InvalidParameterError, match="start_date must be on or before end_date"):
            _validate_dates("2024-01-31", "2024-01-01")

    def test_invalid_date_format_raises(self):
        with pytest.raises(InvalidParameterError, match="Invalid date format"):
            _validate_dates("invalid", "2024-01-31")


class TestValidateSymbol:
    """Tests for _validate_symbol."""

    def test_valid_symbol(self):
        _validate_symbol("US:AAPL")

    def test_empty_symbol_raises(self):
        with pytest.raises(InvalidParameterError, match="symbol must not be empty"):
            _validate_symbol("")

    def test_whitespace_only_symbol_raises(self):
        with pytest.raises(InvalidParameterError, match="symbol must not be empty"):
            _validate_symbol("   ")


class TestValidatePeriod:
    """Tests for _validate_period."""

    def test_valid_periods(self):
        _validate_period("FY")
        _validate_period("Q")

    def test_invalid_period_raises(self):
        with pytest.raises(InvalidParameterError, match="Invalid period"):
            _validate_period("INVALID")


class TestValidateExchange:
    """Tests for _validate_exchange."""

    def test_valid_exchange(self):
        _validate_exchange("US")

    def test_empty_exchange_raises(self):
        with pytest.raises(InvalidParameterError, match="exchange must not be empty"):
            _validate_exchange("")


class TestValidateTradeDate:
    """Tests for _validate_trade_date."""

    def test_valid_trade_date(self):
        _validate_trade_date("2024-01-15")

    def test_invalid_trade_date_raises(self):
        with pytest.raises(InvalidParameterError, match="Invalid trade_date format"):
            _validate_trade_date("invalid")


class TestValidatePriceField:
    """Tests for _validate_price_field."""

    def test_valid_fields(self):
        for field in ["open", "high", "low", "close", "adjusted_close"]:
            _validate_price_field(field)

    def test_invalid_field_raises(self):
        with pytest.raises(InvalidParameterError, match="Invalid field"):
            _validate_price_field("invalid")


class TestGetPrice:
    """Tests for get_price tool."""

    def test_get_price_returns_records(self):
        cache = FakeCacheManager()
        result = get_price(
            symbol="US:AAPL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            cache_manager=cache,
            currency="USD",
        )

        assert len(result) == 1
        assert result[0]["symbol"] == "US:AAPL"
        assert result[0]["close"] == Decimal("104.0")
        assert result[0]["source"] == "openbb:yfinance"

    def test_get_price_without_cache_manager_requires_warehouse(self):
        with pytest.raises(InvalidParameterError, match="warehouse is required"):
            get_price(
                symbol="US:AAPL",
                start_date="2024-01-01",
                end_date="2024-01-31",
            )

    def test_get_price_invalid_dates_raises(self):
        cache = FakeCacheManager()
        with pytest.raises(InvalidParameterError, match="start_date must be on or before"):
            get_price(
                symbol="US:AAPL",
                start_date="2024-01-31",
                end_date="2024-01-01",
                cache_manager=cache,
            )

    def test_get_price_empty_symbol_raises(self):
        cache = FakeCacheManager()
        with pytest.raises(InvalidParameterError, match="symbol must not be empty"):
            get_price(
                symbol="",
                start_date="2024-01-01",
                end_date="2024-01-31",
                cache_manager=cache,
            )


class TestGetFundamentals:
    """Tests for get_fundamentals tool."""

    def test_get_fundamentals_returns_data(self):
        result = get_fundamentals(symbol="US:AAPL")
        assert isinstance(result, list)
        assert len(result) > 0
        # Each record should have source metadata
        for record in result:
            assert "source" in record
            assert "endpoint" in record

    def test_get_fundamentals_invalid_symbol_raises(self):
        with pytest.raises(InvalidParameterError, match="symbol must not be empty"):
            get_fundamentals(symbol="")

    def test_get_fundamentals_invalid_period_raises(self):
        with pytest.raises(InvalidParameterError, match="Invalid period"):
            get_fundamentals(symbol="US:AAPL", period="INVALID")


class TestListSymbols:
    """Tests for list_symbols tool."""

    def test_list_symbols_returns_data(self):
        result = list_symbols(exchange="US")

        assert len(result) >= 1
        assert result[0]["exchange"] == "US"
        assert "symbol" in result[0]

    def test_list_symbols_default_exchange(self):
        result = list_symbols()
        assert len(result) >= 1

    def test_list_symbols_invalid_exchange_raises(self):
        # Mock supported_exchanges to exclude INVALID
        import fincouncil.data.symbols.mapping as symbols_module
        original_supported = symbols_module.supported_exchanges

        def mock_supported():
            return ["US", "SET"]

        symbols_module.supported_exchanges = mock_supported
        try:
            with pytest.raises(InvalidParameterError, match="Unsupported exchange"):
                list_symbols(exchange="INVALID")
        finally:
            symbols_module.supported_exchanges = original_supported


class MultiSourceFakeCacheManager:
    """Fake cache manager that returns different values for different sources."""

    def __init__(self):
        self.openbb_value = Decimal("104.0")
        self.yfinance_value = Decimal("104.05")

    def get_or_fetch(self, symbol, start_date, end_date, adapter, currency, source, force_refresh=False):
        # Return different values based on source to test reconciliation
        value = self.openbb_value if "openbb" in source else self.yfinance_value
        return [
            PriceRecord(
                kind="price",
                symbol=symbol,
                date=start_date,
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("99.0"),
                close=value,
                volume=1000000,
                adjusted_close=value,
                source=source,
                currency=CurrencyCode(currency),
                as_of=date.today(),
            )
        ]


class TestReconcile:
    """Tests for reconcile tool."""

    def test_reconcile_returns_log(self, monkeypatch):
        # Mock adapters to be available
        def mock_is_available(self):
            return True

        monkeypatch.setattr(
            "fincouncil.data.adapters.openbb.OpenBBAdapter.is_available",
            mock_is_available,
        )
        monkeypatch.setattr(
            "fincouncil.data.adapters.yfinance.YFinanceAdapter.is_available",
            mock_is_available,
        )

        cache = MultiSourceFakeCacheManager()

        result = reconcile(
            symbol="US:AAPL",
            field="close",
            trade_date="2024-01-15",
            cache_manager=cache,
        )

        assert result["symbol"] == "US:AAPL"
        assert result["field"] == "close"
        assert result["status"] in [ReconcileStatus.PASS, ReconcileStatus.FLAG]
        assert "values" in result
        assert len(result["values"]) >= 2

    def test_reconcile_invalid_symbol_raises(self):
        cache = FakeCacheManager()
        with pytest.raises(InvalidParameterError, match="symbol must not be empty"):
            reconcile(
                symbol="",
                field="close",
                trade_date="2024-01-15",
                cache_manager=cache,
            )

    def test_reconcile_invalid_date_raises(self):
        cache = FakeCacheManager()
        with pytest.raises(InvalidParameterError, match="Invalid trade_date"):
            reconcile(
                symbol="US:AAPL",
                field="close",
                trade_date="invalid",
                cache_manager=cache,
            )

    def test_reconcile_invalid_field_raises(self):
        cache = FakeCacheManager()
        with pytest.raises(InvalidParameterError, match="Invalid field"):
            reconcile(
                symbol="US:AAPL",
                field="invalid",
                trade_date="2024-01-15",
                cache_manager=cache,
            )

    def test_reconcile_without_cache_manager_requires_warehouse(self):
        with pytest.raises(InvalidParameterError, match="warehouse is required"):
            reconcile(
                symbol="US:AAPL",
                field="close",
                trade_date="2024-01-15",
            )


class TestMCPToolsCanonicalRecords:
    """Integration tests for MCP tools returning canonical records (CP1 requirement T1.10)."""

    def test_get_price_returns_records_with_source_and_currency(self):
        """get_price must return records with source and currency fields."""
        cache = FakeCacheManager()
        result = get_price(
            symbol="US:AAPL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            cache_manager=cache,
            currency="USD",
        )

        assert len(result) >= 1
        for record in result:
            assert "source" in record
            assert "currency" in record
            assert record["source"]
            assert record["currency"]

    def test_get_price_returns_records_with_all_required_fields(self):
        """get_price records must have all OHLCV fields."""
        cache = FakeCacheManager()
        result = get_price(
            symbol="US:AAPL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            cache_manager=cache,
            currency="USD",
        )

        assert len(result) >= 1
        for record in result:
            assert "symbol" in record
            assert "date" in record
            assert "open" in record
            assert "high" in record
            assert "low" in record
            assert "close" in record
            assert "volume" in record
            assert "adjusted_close" in record

    def test_get_price_records_have_correct_currency_code(self):
        """get_price records must have 3-letter ISO currency codes."""
        cache = FakeCacheManager()
        result = get_price(
            symbol="US:AAPL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            cache_manager=cache,
            currency="USD",
        )

        for record in result:
            currency = record["currency"]
            assert len(str(currency)) == 3
            assert str(currency).isalpha()

    def test_list_symbols_returns_valid_metadata(self):
        """list_symbols must return dicts with required metadata fields."""
        result = list_symbols(exchange="US")

        assert len(result) >= 1
        for record in result:
            assert "exchange" in record
            assert "symbol" in record
            assert record["exchange"]

    def test_reconcile_returns_log_with_required_fields(self, monkeypatch):
        """reconcile must return log with all required fields."""
        from decimal import Decimal

        # Mock adapters so is_available() returns True
        # Patch where used, not where defined (reconcile() imports these classes)
        monkeypatch.setattr(
            "fincouncil.data.mcp.tools.OpenBBAdapter.is_available",
            lambda self: True,
        )
        monkeypatch.setattr(
            "fincouncil.data.mcp.tools.YFinanceAdapter.is_available",
            lambda self: True,
        )

        class MultiSourceCache:
            def get_or_fetch(self, symbol, start_date, end_date, adapter, currency, source, force_refresh=False):
                value = Decimal("104.0") if "openbb" in source else Decimal("104.05")
                return [
                    PriceRecord(
                        kind="price",
                        symbol=symbol,
                        date=start_date,
                        open=Decimal("100.0"),
                        high=Decimal("105.0"),
                        low=Decimal("99.0"),
                        close=value,
                        volume=1000000,
                        adjusted_close=value,
                        source=source,
                        currency=CurrencyCode(currency),
                        as_of=date.today(),
                    )
                ]

        cache = MultiSourceCache()

        result = reconcile(
            symbol="US:AAPL",
            field="close",
            trade_date="2024-01-15",
            cache_manager=cache,
        )

        # Verify log has all required fields
        assert "symbol" in result
        assert "field" in result
        assert "date" in result
        assert "values" in result
        assert "status" in result
        assert "threshold_pct" in result
        assert "diff_pct" in result
        assert "explanation" in result
        assert result["source"]
        assert result["currency"]

    def test_reconcile_log_has_source_and_currency(self, monkeypatch):
        """reconcile log must have source and currency for auditability."""
        from decimal import Decimal

        # Mock adapters so is_available() returns True
        # Patch where used, not where defined (reconcile() imports these classes)
        monkeypatch.setattr(
            "fincouncil.data.mcp.tools.OpenBBAdapter.is_available",
            lambda self: True,
        )
        monkeypatch.setattr(
            "fincouncil.data.mcp.tools.YFinanceAdapter.is_available",
            lambda self: True,
        )

        class MultiSourceCache:
            def get_or_fetch(self, symbol, start_date, end_date, adapter, currency, source, force_refresh=False):
                value = Decimal("104.0") if "openbb" in source else Decimal("104.05")
                return [
                    PriceRecord(
                        kind="price",
                        symbol=symbol,
                        date=start_date,
                        open=Decimal("100.0"),
                        high=Decimal("105.0"),
                        low=Decimal("99.0"),
                        close=value,
                        volume=1000000,
                        adjusted_close=value,
                        source=source,
                        currency=CurrencyCode(currency),
                        as_of=date.today(),
                    )
                ]

        cache = MultiSourceCache()

        result = reconcile(
            symbol="US:AAPL",
            field="close",
            trade_date="2024-01-15",
            cache_manager=cache,
        )

        assert result["source"]
        assert result["currency"]
