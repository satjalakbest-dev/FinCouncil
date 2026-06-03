"""Lazy yfinance adapter scaffold for raw Phase 1 provider payloads.

This module intentionally keeps yfinance optional. Unit tests can inject a fake
client and production code can instantiate the adapter without importing yfinance
until a live call is explicitly attempted. The adapter returns raw provider rows
annotated with call metadata; normalization into canonical records belongs in
``fincouncil.data.normalize``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module, util
from typing import Any, Iterable, Mapping, Sequence

from fincouncil.data.adapters.base import BaseAdapter


class YFinanceAdapterError(RuntimeError):
    """Base error for yfinance adapter failures."""


class YFinanceUnavailableError(YFinanceAdapterError):
    """Raised when a live yfinance call is requested but yfinance is unavailable."""


@dataclass(frozen=True)
class FundamentalEndpoint:
    """yfinance endpoint path used for one raw fundamentals slice."""

    name: str
    path: tuple[str, ...]


_DEFAULT_FUNDAMENTAL_ENDPOINTS: tuple[FundamentalEndpoint, ...] = (
    FundamentalEndpoint("info", ("info",)),
    FundamentalEndpoint("financials", ("financials",)),
    FundamentalEndpoint("balance_sheet", ("balance_sheet",)),
    FundamentalEndpoint("cashflow", ("cashflow",)),
)


class YFinanceAdapter(BaseAdapter):
    """Import-optional yfinance adapter for raw prices and global fundamentals.

    Parameters
    ----------
    client:
        Optional injected yfinance-like client. Supplying this avoids importing
        yfinance and is the supported unit-test seam.
    fundamental_endpoints:
        Sequence of fundamental endpoints to fetch. Defaults to standard
        financials, balance sheet, and cashflow endpoints.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        fundamental_endpoints: Sequence[FundamentalEndpoint] = _DEFAULT_FUNDAMENTAL_ENDPOINTS,
    ) -> None:
        self._client = client
        self.fundamental_endpoints = tuple(fundamental_endpoints)

    @property
    def name(self) -> str:
        return "yfinance"

    def is_available(self) -> bool:
        """Return True when an injected client exists or yfinance can be imported."""

        return self._client is not None or util.find_spec("yfinance") is not None

    def get_price(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch raw yfinance EOD price rows for a canonical or provider symbol.

        No fallback or synthetic rows are generated. If yfinance returns an empty
        payload, this method returns an empty list.
        """

        if start > end:
            raise ValueError("start must be on or before end")
        provider_symbol = _to_provider_symbol(symbol)
        client = self._get_client()
        ticker = client.Ticker(provider_symbol)
        hist = ticker.history(start=start.isoformat(), end=end.isoformat())
        response = _coerce_dataframe(hist)
        return _annotate_records(
            response,
            provider_symbol=provider_symbol,
            provider_backend="yfinance",
            provider_call="ticker.history",
        )

    def get_fundamentals(self, symbol: str, period: str = "FY") -> list[dict[str, Any]]:
        """Fetch raw yfinance fundamentals rows across statement endpoints.

        Returns one dict per ``fundamental_endpoints`` entry.  The ``info``
        endpoint yields a single dict of key company metrics (market cap, PE,
        sector, etc.).  The statement endpoints (financials, balance_sheet,
        cashflow) yield column-oriented DataFrames that we restructure as
        one dict per reporting period.

        Each returned dict is annotated with ``source``, ``provider``,
        ``provider_backend``, ``provider_symbol``, and ``provider_call``
        metadata matching the price adapter convention.
        """
        yf = self._get_client()
        provider_symbol = _to_provider_symbol(symbol)
        ticker = yf.Ticker(provider_symbol)
        results: list[dict[str, Any]] = []

        for endpoint in self.fundamental_endpoints:
            try:
                target = ticker
                for attr in endpoint.path:
                    target = getattr(target, attr)

                if endpoint.name == "info":
                    # .info returns a plain dict
                    if target and isinstance(target, dict):
                        row = dict(target)
                        row["endpoint"] = endpoint.name
                        row["symbol"] = symbol
                        row["period"] = period
                        results.append(self._annotate(row, provider_symbol, "ticker.info"))
                else:
                    # .financials / .balance_sheet / .cashflow return DataFrames
                    if target is not None and hasattr(target, "columns"):
                        for col_idx in range(len(target.columns)):
                            period_label = str(target.columns[col_idx])
                            row = {"endpoint": endpoint.name, "symbol": symbol, "period": period_label}
                            for field_name in target.index:
                                val = target.iloc[target.index.get_loc(field_name), col_idx]
                                row[field_name] = val if val == val else None  # NaN guard
                            results.append(self._annotate(row, provider_symbol, f"ticker.{endpoint.path[-1]}"))
            except Exception:
                # Individual endpoint failures should not block others
                continue

        return results

    def _annotate(self, row: dict, provider_symbol: str, call: str) -> dict:
        """Add provider metadata to a raw fundamentals row."""
        row["source"] = f"yfinance:yfinance"
        row["provider"] = "yfinance"
        row["provider_backend"] = "yfinance"
        row["provider_symbol"] = provider_symbol
        row["provider_call"] = call
        return row

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.is_available():
            raise YFinanceUnavailableError(
                "yfinance is not installed; inject a client for tests or install yfinance for live calls"
            )
        module = import_module("yfinance")
        # Cache the client for subsequent calls
        self._client = module
        return self._client


_YAHOO_SUFFIX_BY_EXCHANGE = {
    "US": "",
    "NASDAQ": "",
    "NYSE": "",
    "AMEX": "",
    "JP": ".T",
    "TSE": ".T",
    "TH": ".BK",
    "SET": ".BK",
    "HK": ".HK",
    "HKEX": ".HK",
    "SH": ".SS",
    "SSE": ".SS",
    "SZ": ".SZ",
    "SZSE": ".SZ",
}


def _to_provider_symbol(symbol: str) -> str:
    exchange, ticker = _split_adapter_symbol(symbol)
    suffix = _YAHOO_SUFFIX_BY_EXCHANGE[exchange]
    if suffix == ".HK" and ticker.isdigit():
        ticker = ticker.zfill(5)
    return f"{ticker}{suffix}"


def _split_adapter_symbol(symbol: str) -> tuple[str, str]:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("symbol must not be empty")
    if ":" not in cleaned:
        return "US", cleaned
    exchange, ticker = cleaned.split(":", 1)
    if not exchange or not ticker:
        raise ValueError("canonical symbol must include exchange and ticker")
    if exchange not in _YAHOO_SUFFIX_BY_EXCHANGE:
        raise ValueError(f"unsupported exchange for yfinance adapter: {exchange}")
    return exchange, ticker


def _coerce_dataframe(frame: Any) -> list[Mapping[str, Any]]:
    """Coerce yfinance DataFrame to list of dicts with lowercase keys."""

    if frame is None or frame.empty:
        return []
    if hasattr(frame, "reset_index"):
        frame = frame.reset_index()
    if hasattr(frame, "to_dict"):
        records = frame.to_dict(orient="records")
        # yfinance returns capitalized column names (Open, High, Low, Close, Volume)
        # Convert to lowercase to match adapter contract
        lower_records = []
        for record in records:
            lower_record = {}
            for key, value in record.items():
                lower_key = key.lower()
                lower_record[lower_key] = value
            lower_records.append(lower_record)
        return lower_records
    return _coerce_rows(frame)


def _coerce_rows(response: Any) -> list[Mapping[str, Any]]:
    """Coerce common yfinance response shapes to row mappings without inventing data."""

    if response is None:
        return []
    if hasattr(response, "to_df"):
        frame = response.to_df()
        return _coerce_dataframe(frame)
    if hasattr(response, "results"):
        return _coerce_rows(response.results)
    if isinstance(response, Mapping):
        for key in ("results", "data"):
            value = response.get(key)
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
                return _coerce_rows(value)
        return [response]
    if isinstance(response, Iterable) and not isinstance(response, (str, bytes)):
        rows: list[Mapping[str, Any]] = []
        for item in response:
            if isinstance(item, Mapping):
                rows.append(item)
            elif hasattr(item, "model_dump"):
                rows.append(item.model_dump())
            elif hasattr(item, "dict"):
                rows.append(item.dict())
            else:
                rows.append({"raw": item})
        return rows
    return [{"raw": response}]


def _annotate_records(
    rows: Iterable[Mapping[str, Any]],
    *,
    provider_symbol: str,
    provider_backend: str,
    provider_call: str,
    extra: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        record.setdefault("source", f"yfinance:{provider_backend}")
        record["provider"] = "yfinance"
        record["provider_backend"] = provider_backend
        record["provider_symbol"] = provider_symbol
        record["provider_call"] = provider_call
        if extra:
            record.update(extra)
        annotated.append(record)
    return annotated
