"""Optional AkShare adapter for CN/HK Tier A raw price payloads."""

from __future__ import annotations

from datetime import date
from importlib import import_module, util
from typing import Any


class AkShareAdapterError(RuntimeError):
    pass


class AkShareUnavailableError(AkShareAdapterError):
    pass


class AkShareAdapter:
    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "akshare"

    def is_available(self) -> bool:
        return self._client is not None or util.find_spec("akshare") is not None

    def get_price(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        client = self._get_client()
        exchange, ticker = _split(symbol)
        try:
            if exchange in {"SSE", "SZSE", "SH", "SZ"}:
                frame = client.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="")
            elif exchange in {"HK", "HKEX"}:
                frame = client.stock_hk_hist(symbol=ticker.zfill(5), period="daily", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="")
            else:
                raise ValueError(f"AkShare Tier A supports CN/HK only, got {exchange}")
        except Exception as exc:
            raise AkShareAdapterError(f"AkShare price fetch failed for {symbol}: {exc}") from exc
        return [_annotate(row, symbol) for row in _rows(frame)]

    def get_fundamentals(self, symbol: str, period: str = "FY") -> list[dict[str, Any]]:
        raise NotImplementedError("Deep AkShare fundamentals are deferred from Tier A")

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.is_available():
            raise AkShareUnavailableError("akshare is not installed; inject a client for tests or install it for live calls")
        self._client = import_module("akshare")
        return self._client


def _split(symbol: str) -> tuple[str, str]:
    if ":" not in symbol:
        raise ValueError("canonical symbol must include exchange and ticker")
    exchange, ticker = symbol.upper().split(":", 1)
    return exchange, ticker


def _rows(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    return [dict(row) for row in frame]


_FIELD_MAP = {
    "日期": "date",
    "时间": "date",
    "開盤": "open",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盤": "close",
    "收盘": "close",
    "成交量": "volume",
    "成交額": "turnover",
    "成交额": "turnover",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "漲跌幅": "pct_change",
    "涨跌额": "change",
    "漲跌額": "change",
    "换手率": "turnover_rate",
    "換手率": "turnover_rate",
}


def _canonical_key(key: Any) -> str:
    text = str(key).strip()
    mapped = _FIELD_MAP.get(text)
    if mapped is not None:
        return mapped
    return text.lower().replace(" ", "_")


def _annotate(row: dict[str, Any], symbol: str) -> dict[str, Any]:
    data = {_canonical_key(key): value for key, value in row.items()}
    data.setdefault("source", "akshare:price")
    data.setdefault("provider", "akshare")
    data.setdefault("symbol", symbol)
    return data
