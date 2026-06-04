from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from fincouncil.data.adapters.akshare import AkShareAdapter, AkShareAdapterError
from fincouncil.data.adapters.finnhub import FinnhubAdapter
from fincouncil.data.adapters.fred import FREDAdapter
from fincouncil.data.adapters.tushare import PaidProviderNotEnabledError, TushareAdapter
from fincouncil.data.mcp.tools import get_macro, get_news, get_price, get_sentiment
from fincouncil.data.normalize.macro import normalize_macro_records
from fincouncil.data.normalize.news import normalize_news_records, normalize_sentiment_records
from fincouncil.data.normalize.price import normalize_price_records
from fincouncil.data.schema import (
    CurrencyCode,
    MacroRecord,
    NewsRecord,
    PriceRecord,
    ProviderGapRecord,
    SentimentRecord,
    ValidationError,
    validate_record,
)
from fincouncil.data.store import DuckDBWarehouse


def test_phase2_records_split_audit_from_currency() -> None:
    news = NewsRecord(
        source="finnhub:company-news",
        as_of=datetime(2026, 6, 4, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
        headline="Synthetic headline",
        url="https://example.test/news",
        symbol="US:AAPL",
    )
    sentiment = SentimentRecord(
        source="finnhub:news-sentiment",
        as_of=datetime(2026, 6, 4, tzinfo=timezone.utc),
        observed_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
        symbol="US:AAPL",
        score=Decimal("0.25"),
        scale_min=Decimal("-1"),
        scale_max=Decimal("1"),
        channel="aggregate",
    )
    macro = MacroRecord(
        source="fred:series_observations",
        as_of=datetime(2026, 6, 4, tzinfo=timezone.utc),
        observation_date=date(2026, 5, 1),
        indicator="CPIAUCSL",
        value=Decimal("313.14"),
        unit="index",
        region="US",
        frequency="monthly",
        series_id="CPIAUCSL",
    )

    for record in (news, sentiment, macro):
        validate_record(record)
        assert not hasattr(record, "currency") or record.currency is None


def test_monetary_record_still_requires_valid_currency() -> None:
    rec = PriceRecord(
        source="test",
        currency=CurrencyCode("XXX"),
        as_of=date(2026, 6, 4),
        symbol="US:AAPL",
        date=date(2026, 6, 4),
        open=Decimal("1"),
        high=Decimal("1"),
        low=Decimal("1"),
        close=Decimal("1"),
        volume=1,
        adjusted_close=Decimal("1"),
    )
    with pytest.raises(ValidationError):
        validate_record(rec)


def test_warehouse_phase2_tables_round_trip(tmp_path: Path) -> None:
    wh = DuckDBWarehouse(tmp_path / "phase2.duckdb")
    try:
        assert wh.upsert_news([
            {"source": "finnhub:company-news", "as_of": datetime.now(), "published_at": datetime.now(), "headline": "h"}
        ]) == 1
        assert wh.upsert_sentiment([
            {"source": "finnhub:news-sentiment", "as_of": datetime.now(), "observed_at": datetime.now(), "symbol": "US:AAPL", "score": 0.1, "scale_min": -1, "scale_max": 1, "channel": "aggregate"}
        ]) == 1
        assert wh.upsert_macro([
            {"source": "fred:series_observations", "as_of": datetime.now(), "observation_date": date(2026, 1, 1), "indicator": "CPI", "value": 1.0, "unit": "index", "region": "US", "frequency": "monthly"}
        ]) == 1
        assert wh.insert_provider_gap_log([
            {"source": "fallback:audit", "as_of": datetime.now(), "status": "FALLBACK_USED", "primary_source": "akshare", "fallback_source": "yfinance", "symbol": "HKEX:00700", "record_count": 2}
        ]) == 1
        assert wh.table_count("news") == 1
        assert wh.table_count("sentiment") == 1
        assert wh.table_count("macro") == 1
        assert wh.table_count("provider_gap_log") == 1
    finally:
        wh.close()


class FakeFinnhubClient:
    def company_news(self, symbol, _from, to):
        return [{"headline": "Synthetic news", "datetime": 1780570000, "url": "https://example.test", "symbol": symbol}]

    def news_sentiment(self, symbol):
        return {"symbol": symbol, "score": "0.2", "scale_min": "-1", "scale_max": "1", "channel": "reddit"}


class FakeFREDClient:
    def series_observations(self, series_id, **kwargs):
        return [{"date": "2026-01-01", "value": "3.14", "series_id": series_id}]


def test_finnhub_fake_client_mcp_news_and_sentiment() -> None:
    adapter = FinnhubAdapter(client=FakeFinnhubClient())
    news = get_news("US:AAPL", "2026-01-01", "2026-01-31", adapter=adapter)
    sentiment = get_sentiment("US:AAPL", adapter=adapter)
    assert news[0]["source"] == "finnhub:company-news"
    assert news[0]["headline"] == "Synthetic news"
    assert sentiment[0]["source"] == "finnhub:news-sentiment"
    assert sentiment[0]["channel"] == "reddit"


def test_fred_fake_client_mcp_macro() -> None:
    rows = get_macro("CPIAUCSL", indicator="CPI", unit="index", region="US", frequency="monthly", adapter=FREDAdapter(client=FakeFREDClient()))
    assert rows[0]["source"] == "fred:series_observations"
    assert rows[0]["unit"] == "index"
    assert rows[0]["currency"] is None


class FakeAkShareClient:
    def stock_zh_a_hist(self, **kwargs):
        return pd.DataFrame([{"日期": "2026-01-02", "开盘": 9.5, "最高": 10.5, "最低": 9.0, "收盘": 10.0, "成交量": 1000}])

    def stock_hk_hist(self, **kwargs):
        return pd.DataFrame([{"日期": "2026-01-02", "开盘": 19.5, "最高": 20.5, "最低": 19.0, "收盘": 20.0, "成交量": 2000}])


class FailingAkShareClient:
    def stock_hk_hist(self, **kwargs):
        raise RuntimeError("blocked")


def test_akshare_fake_client_cn_hk_and_failure() -> None:
    adapter = AkShareAdapter(client=FakeAkShareClient())
    assert adapter.get_price("SSE:600000", date(2026, 1, 1), date(2026, 1, 3))[0]["source"] == "akshare:price"
    assert adapter.get_price("HKEX:00700", date(2026, 1, 1), date(2026, 1, 3))[0]["provider"] == "akshare"
    with pytest.raises(AkShareAdapterError):
        AkShareAdapter(client=FailingAkShareClient()).get_price("HKEX:00700", date(2026, 1, 1), date(2026, 1, 3))


def test_akshare_rows_normalize_to_canonical_price_records() -> None:
    rows = AkShareAdapter(client=FakeAkShareClient()).get_price(
        "HKEX:00700",
        date(2026, 1, 1),
        date(2026, 1, 3),
    )

    records = normalize_price_records(
        rows,
        symbol="HKEX:00700",
        source="akshare:price",
        currency="HKD",
        as_of=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert records[0].source == "akshare:price"
    assert records[0].currency == CurrencyCode("HKD")
    assert records[0].close == Decimal("20.0")


def test_provider_gap_record_captures_fallback_provenance() -> None:
    rec = ProviderGapRecord(
        source="fallback:audit",
        as_of=datetime.now(timezone.utc),
        status="FALLBACK_USED",
        primary_source="akshare",
        fallback_source="yfinance",
        error_type="AkShareAdapterError",
        failure_reason="blocked",
        symbol="HKEX:00700",
        market="HKEX",
        record_count=2,
    )
    validate_record(rec)
    assert rec.primary_source == "akshare"
    assert rec.fallback_source == "yfinance"


def test_tushare_paid_hook_is_explicit() -> None:
    with pytest.raises(PaidProviderNotEnabledError, match="paid/not enabled"):
        TushareAdapter().get_fundamentals("SSE:600000")

class _FakeCollectedItem:
    def __init__(self, keywords, nodeid="fincouncil/tests/test_other_provider.py::test_case"):
        self.keywords = set(keywords)
        self.nodeid = nodeid
        self.added_markers = []

    def add_marker(self, marker):
        self.added_markers.append(marker)


def _skip_reasons(item):
    return [marker.kwargs.get("reason", "") for marker in item.added_markers]


def test_akshare_live_marker_requires_provider_specific_opt_in(monkeypatch):
    import fincouncil.tests.conftest as suite_conftest

    monkeypatch.setenv("OPENAI_API_KEY", "dummy-unrelated-key")
    monkeypatch.delenv(suite_conftest.AKSHARE_LIVE_ENV, raising=False)
    item = _FakeCollectedItem({"live", "akshare"})

    suite_conftest.pytest_collection_modifyitems(None, [item])

    assert _skip_reasons(item) == [suite_conftest.AKSHARE_LIVE_SKIP_REASON]


def test_akshare_missing_marker_cases_are_rejected(monkeypatch):
    import fincouncil.tests.conftest as suite_conftest

    monkeypatch.setenv(suite_conftest.AKSHARE_LIVE_ENV, "1")
    marker_only = _FakeCollectedItem({"akshare"})
    live_only = _FakeCollectedItem({"live"}, nodeid="fincouncil/tests/test_akshare_adapter.py::test_live")

    suite_conftest.pytest_collection_modifyitems(None, [marker_only, live_only])

    assert _skip_reasons(marker_only) == [suite_conftest.AKSHARE_MARKER_CONTRACT_SKIP_REASON]
    assert _skip_reasons(live_only) == [suite_conftest.AKSHARE_MARKER_CONTRACT_SKIP_REASON]

class FakeYFinanceFallbackClient:
    def get_price(self, symbol, start, end):
        return [{"date": "2026-01-02", "open": 19.5, "high": 20.5, "low": 19.0, "close": 20.0, "volume": 2000, "source": "yfinance:yfinance"}]


def test_akshare_failure_falls_back_to_yfinance_with_audit() -> None:
    from fincouncil.data.fallback import get_price_with_akshare_yfinance_fallback

    rows, audit = get_price_with_akshare_yfinance_fallback(
        "HKEX:00700",
        date(2026, 1, 1),
        date(2026, 1, 3),
        akshare_adapter=AkShareAdapter(client=FailingAkShareClient()),
        yfinance_adapter=FakeYFinanceFallbackClient(),
    )

    assert rows[0]["source"] == "fallback:akshare_to_yfinance"
    assert rows[0]["fallback_source"] == "yfinance"
    assert audit is not None
    assert audit.primary_source == "akshare"
    assert audit.record_count == 1


def test_mcp_cn_hk_price_fallback_persists_provider_gap(tmp_path: Path) -> None:
    wh = DuckDBWarehouse(tmp_path / "fallback.duckdb")
    try:
        rows = get_price(
            "HKEX:00700",
            "2026-01-01",
            "2026-01-03",
            warehouse=wh,
            adapter=AkShareAdapter(client=FailingAkShareClient()),
            fallback_adapter=FakeYFinanceFallbackClient(),
        )

        assert rows[0]["source"] == "fallback:akshare_to_yfinance"
        assert rows[0]["currency"] == CurrencyCode("HKD")
        assert wh.table_count("prices") == 1
        assert wh.table_count("provider_gap_log") == 1
    finally:
        wh.close()

def _pairwise_pct(values):
    max_val = max(values)
    min_val = min(values)
    mean_val = (max_val + min_val) / Decimal("2")
    return abs(max_val - min_val) / abs(mean_val) * Decimal("100")


def test_cn_hk_reconcile_discrepancy_crosscheck() -> None:
    from fincouncil.data.reconcile.engine import ReconcileEngine
    from fincouncil.data.schema import ReconcileStatus

    engine = ReconcileEngine()
    for symbol, currency in [("SSE:600000", "CNY"), ("HKEX:00700", "HKD")]:
        values = {"akshare": Decimal("100.00"), "yfinance": Decimal("96.00")}
        record = engine.reconcile(
            symbol=symbol,
            field="close",
            as_of=date(2026, 1, 2),
            currency=CurrencyCode(currency),
            values_by_source=values,
            record_kind="price",
        )
        assert record.status == ReconcileStatus.FLAG
        assert record.diff_pct == _pairwise_pct(list(values.values()))
        validate_record(record)


def test_finnhub_and_fred_live_markers_require_exact_keys(monkeypatch):
    import fincouncil.tests.conftest as suite_conftest

    monkeypatch.setenv("OPENAI_API_KEY", "dummy-unrelated-key")
    monkeypatch.delenv(suite_conftest.FINNHUB_KEY_ENV, raising=False)
    monkeypatch.delenv(suite_conftest.FRED_KEY_ENV, raising=False)
    finnhub_item = _FakeCollectedItem({"live", "finnhub"})
    fred_item = _FakeCollectedItem({"live", "fred"})

    suite_conftest.pytest_collection_modifyitems(None, [finnhub_item, fred_item])

    assert _skip_reasons(finnhub_item) == [suite_conftest.FINNHUB_SKIP_REASON]
    assert _skip_reasons(fred_item) == [suite_conftest.FRED_SKIP_REASON]
