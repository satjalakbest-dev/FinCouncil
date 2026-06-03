from __future__ import annotations

from datetime import date

import pytest

from fincouncil.data.adapters.openbb import OpenBBAdapter, OpenBBUnavailableError


class _Endpoint:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(kwargs)
        return self.rows


class _Namespace:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def _fake_client() -> tuple[_Namespace, dict[str, _Endpoint]]:
    endpoints = {
        "historical": _Endpoint(
            [
                {
                    "date": "2026-06-01",
                    "open": 30.0,
                    "high": 31.0,
                    "low": 29.5,
                    "close": 30.5,
                    "volume": 1000,
                }
            ]
        ),
        "income": _Endpoint([{"fiscal_date": "2025-12-31", "revenue": 100.0}]),
        "balance": _Endpoint([{"fiscal_date": "2025-12-31", "total_assets": 200.0}]),
        "cash": _Endpoint([{"fiscal_date": "2025-12-31", "operating_cash_flow": 30.0}]),
        "ratios": _Endpoint([{"fiscal_date": "2025-12-31", "pe_ratio": 20.0}]),
    }
    client = _Namespace(
        equity=_Namespace(
            price=_Namespace(historical=endpoints["historical"]),
            fundamental=_Namespace(
                income=endpoints["income"],
                balance=endpoints["balance"],
                cash=endpoints["cash"],
                ratios=endpoints["ratios"],
            ),
        )
    )
    return client, endpoints


def test_openbb_price_adapter_uses_injected_client_and_keeps_raw_payload() -> None:
    client, endpoints = _fake_client()
    adapter = OpenBBAdapter(client=client)

    rows = adapter.get_price("SET:PTT", date(2026, 6, 1), date(2026, 6, 2))

    assert rows == [
        {
            "date": "2026-06-01",
            "open": 30.0,
            "high": 31.0,
            "low": 29.5,
            "close": 30.5,
            "volume": 1000,
            "source": "openbb:yfinance",
            "provider": "openbb",
            "provider_backend": "yfinance",
            "provider_symbol": "PTT.BK",
            "provider_call": "equity.price.historical",
        }
    ]
    assert endpoints["historical"].calls == [
        {
            "symbol": "PTT.BK",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "provider": "yfinance",
        }
    ]


def test_openbb_fundamentals_adapter_collects_us_statement_endpoints() -> None:
    client, endpoints = _fake_client()
    adapter = OpenBBAdapter(client=client, fundamentals_provider="fmp")

    rows = adapter.get_fundamentals("US:AAPL", period="FY")

    assert [row["fundamental_endpoint"] for row in rows] == ["income", "balance", "cash", "ratios"]
    assert {row["source"] for row in rows} == {"openbb:fmp"}
    assert {row["provider_symbol"] for row in rows} == {"AAPL"}
    assert endpoints["income"].calls == [{"symbol": "AAPL", "period": "FY", "provider": "fmp"}]
    assert endpoints["ratios"].calls == [{"symbol": "AAPL", "period": "FY", "provider": "fmp"}]


def test_openbb_fundamentals_reject_non_us_symbol_without_fabricating_data() -> None:
    client, _endpoints = _fake_client()
    adapter = OpenBBAdapter(client=client)

    with pytest.raises(ValueError, match="US symbols only"):
        adapter.get_fundamentals("SET:PTT")


def test_openbb_adapter_is_import_optional_until_live_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fincouncil.data.adapters.openbb.util.find_spec", lambda _name: None)
    adapter = OpenBBAdapter()

    assert adapter.is_available() is False
    with pytest.raises(OpenBBUnavailableError, match="OpenBB is not installed"):
        adapter.get_price("US:AAPL", date(2026, 6, 1), date(2026, 6, 1))


def test_openbb_adapter_validates_date_range_before_provider_call() -> None:
    client, endpoints = _fake_client()
    adapter = OpenBBAdapter(client=client)

    with pytest.raises(ValueError, match="start must be"):
        adapter.get_price("US:AAPL", date(2026, 6, 2), date(2026, 6, 1))

    assert endpoints["historical"].calls == []
