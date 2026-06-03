"""Lazy OpenBB adapter scaffold for raw Phase 1 provider payloads.

This module intentionally keeps OpenBB optional. Unit tests can inject a fake
client and production code can instantiate the adapter without importing OpenBB
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
class OpenBBAdapterError(RuntimeError):
    """Base error for OpenBB adapter failures."""


class OpenBBUnavailableError(OpenBBAdapterError):
    """Raised when a live OpenBB call is requested but OpenBB is unavailable."""


@dataclass(frozen=True)
class FundamentalEndpoint:
    """OpenBB endpoint path used for one raw fundamentals slice."""

    name: str
    path: tuple[str, ...]


_DEFAULT_FUNDAMENTAL_ENDPOINTS: tuple[FundamentalEndpoint, ...] = (
    FundamentalEndpoint("income", ("equity", "fundamental", "income")),
    FundamentalEndpoint("balance", ("equity", "fundamental", "balance")),
    FundamentalEndpoint("cash", ("equity", "fundamental", "cash")),
    FundamentalEndpoint("ratios", ("equity", "fundamental", "ratios")),
)
_PRICE_ENDPOINT_PATH = ("equity", "price", "historical")


class OpenBBAdapter(BaseAdapter):
    """Import-optional OpenBB adapter for raw prices and US fundamentals.

    Parameters
    ----------
    client:
        Optional injected OpenBB-like client. Supplying this avoids importing
        OpenBB and is the supported unit-test seam.
    price_provider:
        OpenBB backend provider for EOD prices. ``yfinance`` is free-first and
        matches the Phase 1 data-source policy.
    fundamentals_provider:
        OpenBB backend provider for fundamentals. If omitted, ``price_provider``
        is reused.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        price_provider: str = "yfinance",
        fundamentals_provider: str | None = None,
        fundamental_endpoints: Sequence[FundamentalEndpoint] = _DEFAULT_FUNDAMENTAL_ENDPOINTS,
    ) -> None:
        self._client = client
        self.price_provider = price_provider
        self.fundamentals_provider = fundamentals_provider or price_provider
        self.fundamental_endpoints = tuple(fundamental_endpoints)

    @property
    def name(self) -> str:
        return "openbb"

    def is_available(self) -> bool:
        """Return True when an injected client exists or OpenBB can be imported."""

        return self._client is not None or util.find_spec("openbb") is not None

    def get_price(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch raw OpenBB EOD price rows for a canonical or provider symbol.

        No fallback or synthetic rows are generated. If OpenBB returns an empty
        payload, this method returns an empty list.
        """

        if start > end:
            raise ValueError("start must be on or before end")
        provider_symbol = _to_provider_symbol(symbol)
        response = self._call_endpoint(
            _PRICE_ENDPOINT_PATH,
            symbol=provider_symbol,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            provider=self.price_provider,
        )
        return _annotate_records(
            _coerce_rows(response),
            provider_symbol=provider_symbol,
            provider_backend=self.price_provider,
            provider_call="equity.price.historical",
        )

    def get_fundamentals(self, symbol: str, period: str = "FY") -> list[dict[str, Any]]:
        """Fetch raw OpenBB US fundamentals rows across statement endpoints.

        Phase 1 scope only promises US fundamentals. Non-US canonical symbols are
        rejected rather than silently fabricating unsupported data.
        """

        exchange, _ticker = _split_adapter_symbol(symbol)
        if exchange != "US":
            raise ValueError("OpenBB fundamentals scaffold currently supports US symbols only")

        provider_symbol = _to_provider_symbol(symbol)
        rows: list[dict[str, Any]] = []
        for endpoint in self.fundamental_endpoints:
            response = self._call_endpoint(
                endpoint.path,
                symbol=provider_symbol,
                period=period,
                provider=self.fundamentals_provider,
            )
            rows.extend(
                _annotate_records(
                    _coerce_rows(response),
                    provider_symbol=provider_symbol,
                    provider_backend=self.fundamentals_provider,
                    provider_call=".".join(endpoint.path),
                    extra={"fundamental_endpoint": endpoint.name, "period": period},
                )
            )
        return rows

    def _call_endpoint(self, path: Sequence[str], **kwargs: Any) -> Any:
        endpoint = _resolve_endpoint(self._get_client(), path)
        return endpoint(**kwargs)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.is_available():
            raise OpenBBUnavailableError(
                "OpenBB is not installed; inject a client for tests or install/configure OpenBB for live calls"
            )
        module = import_module("openbb")
        try:
            self._client = module.obb
        except AttributeError as exc:
            raise OpenBBUnavailableError("openbb module does not expose the expected 'obb' client") from exc
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
        raise ValueError(f"unsupported exchange for OpenBB adapter: {exchange}")
    return exchange, ticker


def _resolve_endpoint(client: Any, path: Sequence[str]) -> Any:
    current = client
    for part in path:
        try:
            current = getattr(current, part)
        except AttributeError as exc:
            dotted = ".".join(path)
            raise OpenBBAdapterError(f"OpenBB client is missing endpoint {dotted!r}") from exc
    if not callable(current):
        dotted = ".".join(path)
        raise OpenBBAdapterError(f"OpenBB endpoint {dotted!r} is not callable")
    return current


def _coerce_rows(response: Any) -> list[Mapping[str, Any]]:
    """Coerce common OpenBB response shapes to row mappings without inventing data."""

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


def _coerce_dataframe(frame: Any) -> list[Mapping[str, Any]]:
    if hasattr(frame, "reset_index"):
        frame = frame.reset_index()
    if hasattr(frame, "to_dict"):
        return frame.to_dict(orient="records")
    return _coerce_rows(frame)


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
        record.setdefault("source", f"openbb:{provider_backend}")
        record["provider"] = "openbb"
        record["provider_backend"] = provider_backend
        record["provider_symbol"] = provider_symbol
        record["provider_call"] = provider_call
        if extra:
            record.update(extra)
        annotated.append(record)
    return annotated
