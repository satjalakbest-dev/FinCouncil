"""Tests for yfinance adapter following the openbb adapter test pattern."""

from datetime import date
from unittest.mock import MagicMock

import pytest

import fincouncil.tests.conftest as suite_conftest

from fincouncil.data.adapters.yfinance import (
    YFinanceAdapter,
    YFinanceAdapterError,
    YFinanceUnavailableError,
    _split_adapter_symbol,
    _to_provider_symbol,
)


class FakeYFinanceClient:
    """Fake yfinance client for testing."""

    class FakeTicker:
        def __init__(self, symbol: str):
            self.symbol = symbol
            self.info = {"totalRevenue": 100000, "netIncome": 20000, "sector": "Technology"}
            import pandas as pd
            self.financials = pd.DataFrame(
                {"Total Revenue": [100000, 90000], "Net Income": [20000, 18000]},
                index=pd.Index(["Total Revenue", "Net Income"]),
                columns=pd.to_datetime(["2024-12-31", "2023-12-31"]),
            )
            self.balance_sheet = pd.DataFrame(
                {"Total Assets": [500000, 450000]},
                index=pd.Index(["Total Assets"]),
                columns=pd.to_datetime(["2024-12-31"]),
            )
            self.cashflow = pd.DataFrame(
                {"Operating Cash Flow": [30000, 25000]},
                index=pd.Index(["Operating Cash Flow"]),
                columns=pd.to_datetime(["2024-12-31", "2023-12-31"]),
            )

        def history(self, start: str, end: str):
            """Return fake price data as DataFrame-like object."""
            import pandas as pd

            data = {
                "Open": [100.0, 101.0],
                "High": [105.0, 106.0],
                "Low": [99.0, 100.0],
                "Close": [104.0, 105.0],
                "Volume": [1000000, 1100000],
            }
            df = pd.DataFrame(data, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
            df.index.name = "Date"
            return df

    def Ticker(self, symbol: str):
        return self.FakeTicker(symbol)


class TestYFinanceAdapterName:
    """Tests for adapter name property."""

    def test_name_returns_yfinance(self):
        adapter = YFinanceAdapter()
        assert adapter.name == "yfinance"


class TestYFinanceIsAvailable:
    """Tests for is_available method."""

    def test_is_available_with_injected_client(self):
        adapter = YFinanceAdapter(client=FakeYFinanceClient())
        assert adapter.is_available() is True

    def test_is_available_without_yfinance_installed(self, monkeypatch):
        # Simulate yfinance not being available
        monkeypatch.delattr("importlib.util.spec_finders", raising=False)

        # Mock find_spec to return None for yfinance
        def mock_find_spec(name):
            if name == "yfinance":
                return None
            # For other modules, return something truthy
            return MagicMock()

        import importlib.util
        monkeypatch.setattr(importlib.util, "find_spec", mock_find_spec)

        adapter = YFinanceAdapter()
        assert adapter.is_available() is False


class TestYFinanceGetPrice:
    """Tests for get_price method."""

    def test_get_price_with_mock_client(self):
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("US:AAPL", date(2024, 1, 1), date(2024, 1, 31))

        assert len(result) == 2
        # Check that records have lowercase keys
        record = result[0]
        assert "date" in record
        assert "open" in record
        assert "high" in record
        assert "low" in record
        assert "close" in record
        assert "volume" in record
        # Check source annotation
        assert record["provider"] == "yfinance"
        assert record["provider_backend"] == "yfinance"
        assert record["provider_symbol"] == "AAPL"
        assert record["provider_call"] == "ticker.history"

    def test_get_price_start_after_end_raises(self):
        adapter = YFinanceAdapter(client=FakeYFinanceClient())
        with pytest.raises(ValueError, match="start must be on or before end"):
            adapter.get_price("US:AAPL", date(2024, 1, 31), date(2024, 1, 1))

    def test_get_price_without_yfinance_raises(self, monkeypatch):
        # Mock find_spec to simulate yfinance not available
        def mock_find_spec(name):
            if name == "yfinance":
                return None
            return MagicMock()

        import importlib.util
        monkeypatch.setattr(importlib.util, "find_spec", mock_find_spec)

        adapter = YFinanceAdapter()
        with pytest.raises(YFinanceUnavailableError, match="yfinance is not installed"):
            adapter.get_price("US:AAPL", date(2024, 1, 1), date(2024, 1, 31))


class TestYFinanceGetFundamentals:
    """Tests for get_fundamentals method."""

    def test_get_fundamentals_returns_records(self):
        adapter = YFinanceAdapter(client=FakeYFinanceClient())
        results = adapter.get_fundamentals("US:AAPL")
        assert isinstance(results, list)
        assert len(results) > 0
        for r in results:
            assert "source" in r
            assert r["source"] == "yfinance:yfinance"
            assert "endpoint" in r
            assert "symbol" in r
            assert "provider" in r


class TestSymbolConversion:
    """Tests for symbol conversion from canonical to yfinance format."""

    @pytest.mark.parametrize(
        "input_symbol,expected_exchange,expected_ticker,expected_provider",
        [
            ("US:AAPL", "US", "AAPL", "AAPL"),
            ("AAPL", "US", "AAPL", "AAPL"),
            ("SET:PTT", "SET", "PTT", "PTT.BK"),
            ("TH:PTT", "TH", "PTT", "PTT.BK"),
            ("HK:700", "HK", "700", "00700.HK"),
            ("HKEX:0005", "HKEX", "0005", "00005.HK"),
            ("JP:7011", "JP", "7011", "7011.T"),
            ("TSE:7203", "TSE", "7203", "7203.T"),
            ("SH:600000", "SH", "600000", "600000.SS"),
            ("SSE:600000", "SSE", "600000", "600000.SS"),
            ("SZ:000001", "SZ", "000001", "000001.SZ"),
            ("SZSE:000001", "SZSE", "000001", "000001.SZ"),
        ],
    )
    def test_to_provider_symbol(
        self, input_symbol, expected_exchange, expected_ticker, expected_provider
    ):
        exchange, ticker = _split_adapter_symbol(input_symbol)
        assert exchange == expected_exchange
        assert ticker == expected_ticker
        provider_symbol = _to_provider_symbol(input_symbol)
        assert provider_symbol == expected_provider

    def test_split_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol must not be empty"):
            _split_adapter_symbol("")

    def test_split_symbol_with_only_exchange_raises(self):
        with pytest.raises(ValueError, match="must include exchange and ticker"):
            _split_adapter_symbol("US:")

    def test_split_symbol_with_only_ticker_raises(self):
        with pytest.raises(ValueError, match="must include exchange and ticker"):
            _split_adapter_symbol(":AAPL")

    def test_unsupported_exchange_raises(self):
        with pytest.raises(ValueError, match="unsupported exchange"):
            _split_adapter_symbol("LON:BARC")


class TestSourceAnnotation:
    """Tests for source metadata annotation on records."""

    def test_records_include_source_annotation(self):
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("US:AAPL", date(2024, 1, 1), date(2024, 1, 31))

        for record in result:
            assert "source" in record
            assert record["source"] == "yfinance:yfinance"
            assert record["provider"] == "yfinance"
            assert record["provider_backend"] == "yfinance"
            assert record["provider_symbol"] == "AAPL"
            assert record["provider_call"] == "ticker.history"


class TestInvalidSymbolHandling:
    """Tests for handling of invalid symbols."""

    def test_get_price_with_empty_symbol_raises(self):
        adapter = YFinanceAdapter(client=FakeYFinanceClient())
        with pytest.raises(ValueError, match="symbol must not be empty"):
            adapter.get_price("", date(2024, 1, 1), date(2024, 1, 31))

    def test_get_price_with_whitespace_only_symbol_raises(self):
        adapter = YFinanceAdapter(client=FakeYFinanceClient())
        with pytest.raises(ValueError, match="symbol must not be empty"):
            adapter.get_price("   ", date(2024, 1, 1), date(2024, 1, 31))

    def test_get_price_with_unsupported_exchange_raises(self):
        adapter = YFinanceAdapter(client=FakeYFinanceClient())
        with pytest.raises(ValueError, match="unsupported exchange"):
            adapter.get_price("LON:BARC", date(2024, 1, 1), date(2024, 1, 31))


class TestYFinanceAdapterContractAcrossMarkets:
    """Offline contract tests using fake yfinance-shaped responses.

    These tests verify adapter record shape and provider-symbol mapping across
    representative markets. They intentionally use ``FakeYFinanceClient`` and
    must remain always-on; true yfinance network tests require both
    ``@pytest.mark.live`` and ``@pytest.mark.yfinance`` plus ``YFINANCE_LIVE=1``.
    """

    def test_us_ticker_returns_valid_data(self):
        """US ticker (AAPL) returns valid price data with required fields."""
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("US:AAPL", date(2024, 1, 2), date(2024, 1, 3))

        assert len(result) == 2
        for record in result:
            # Verify all required fields exist
            assert "date" in record
            assert "open" in record
            assert "high" in record
            assert "low" in record
            assert "close" in record
            assert "volume" in record
            # Verify source metadata
            assert record["provider"] == "yfinance"
            assert record["provider_symbol"] == "AAPL"
            assert record["provider_call"] == "ticker.history"

    def test_thai_ticker_returns_valid_data(self):
        """Thai ticker (PTT.BK) returns valid price data with .BK suffix."""
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("SET:PTT", date(2024, 1, 2), date(2024, 1, 3))

        assert len(result) == 2
        for record in result:
            assert record["provider_symbol"] == "PTT.BK"
            assert record["provider"] == "yfinance"

    def test_hk_ticker_zero_padded_returns_valid_data(self):
        """HK ticker (700) gets zero-padded to 00700.HK."""
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("HK:700", date(2024, 1, 2), date(2024, 1, 3))

        assert len(result) == 2
        for record in result:
            assert record["provider_symbol"] == "00700.HK"
            assert record["provider"] == "yfinance"

    def test_japanese_ticker_returns_valid_data(self):
        """Japanese ticker (7203.T) returns valid price data."""
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("JP:7203", date(2024, 1, 2), date(2024, 1, 3))

        assert len(result) == 2
        for record in result:
            assert record["provider_symbol"] == "7203.T"
            assert record["provider"] == "yfinance"

    def test_chinese_sse_ticker_returns_valid_data(self):
        """Chinese SSE ticker (600000.SS) returns valid price data."""
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("SH:600000", date(2024, 1, 2), date(2024, 1, 3))

        assert len(result) == 2
        for record in result:
            assert record["provider_symbol"] == "600000.SS"
            assert record["provider"] == "yfinance"

    def test_chinese_szse_ticker_returns_valid_data(self):
        """Chinese SZSE ticker (000001.SZ) returns valid price data."""
        client = FakeYFinanceClient()
        adapter = YFinanceAdapter(client=client)

        result = adapter.get_price("SZ:000001", date(2024, 1, 2), date(2024, 1, 3))

        assert len(result) == 2
        for record in result:
            assert record["provider_symbol"] == "000001.SZ"
            assert record["provider"] == "yfinance"


class _FakeCollectedItem:
    """Small pytest item stand-in for testing collection marker policy."""

    def __init__(
        self,
        keywords,
        nodeid="fincouncil/tests/test_other_provider.py::test_case",
    ):
        self.keywords = set(keywords)
        self.nodeid = nodeid
        self.added_markers = []

    def add_marker(self, marker):
        self.added_markers.append(marker)


def _skip_reasons(item):
    return [marker.kwargs.get("reason", "") for marker in item.added_markers]


def _clear_provider_credentials(monkeypatch):
    for env_var in suite_conftest.CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_yfinance_contract_tests_are_not_live_marked():
    """Fake-client yfinance contract tests must run in default offline pytest."""
    assert not hasattr(TestYFinanceAdapterContractAcrossMarkets, "pytestmark")


def test_yfinance_live_marker_requires_provider_specific_opt_in(monkeypatch):
    """Unrelated credentials must not enable yfinance live tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-unrelated-key")
    monkeypatch.delenv(suite_conftest.YFINANCE_LIVE_ENV, raising=False)
    item = _FakeCollectedItem({"live", "yfinance"})

    suite_conftest.pytest_collection_modifyitems(None, [item])

    assert _skip_reasons(item) == [suite_conftest.YFINANCE_LIVE_SKIP_REASON]


def test_yfinance_live_marker_runs_when_explicitly_enabled(monkeypatch):
    """The future yfinance live contract is YFINANCE_LIVE=1 + live+yfinance."""
    _clear_provider_credentials(monkeypatch)
    monkeypatch.setenv(suite_conftest.YFINANCE_LIVE_ENV, "1")
    item = _FakeCollectedItem({"live", "yfinance"})

    suite_conftest.pytest_collection_modifyitems(None, [item])

    assert item.added_markers == []


def test_credentialed_live_marker_still_uses_provider_credentials(monkeypatch):
    """Non-yfinance live tests keep the existing credential-gated behavior."""
    _clear_provider_credentials(monkeypatch)
    monkeypatch.delenv(suite_conftest.YFINANCE_LIVE_ENV, raising=False)
    item = _FakeCollectedItem({"live"})

    suite_conftest.pytest_collection_modifyitems(None, [item])

    assert _skip_reasons(item) == [suite_conftest.MISSING_CREDENTIALS_SKIP_REASON]


def test_yfinance_marker_without_live_is_rejected(monkeypatch):
    """Future yfinance network tests must not use yfinance marker alone."""
    monkeypatch.setenv(suite_conftest.YFINANCE_LIVE_ENV, "1")
    item = _FakeCollectedItem({"yfinance"})

    suite_conftest.pytest_collection_modifyitems(None, [item])

    assert _skip_reasons(item) == [suite_conftest.YFINANCE_MARKER_CONTRACT_SKIP_REASON]


def test_yfinance_file_live_marker_without_yfinance_is_rejected(monkeypatch):
    """A live test in yfinance test files must also carry the yfinance marker."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-unrelated-key")
    item = _FakeCollectedItem(
        {"live"},
        nodeid="fincouncil/tests/test_yfinance_adapter.py::test_future_live",
    )

    suite_conftest.pytest_collection_modifyitems(None, [item])

    assert _skip_reasons(item) == [suite_conftest.YFINANCE_MARKER_CONTRACT_SKIP_REASON]
