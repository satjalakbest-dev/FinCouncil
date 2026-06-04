"""Optional Finnhub adapter for free-tier news and sentiment payloads."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


class FinnhubAdapterError(RuntimeError):
    pass


class FinnhubUnavailableError(FinnhubAdapterError):
    pass


class FinnhubAdapter:
    def __init__(self, *, api_key: str | None = None, client: Any | None = None, base_url: str = "https://finnhub.io/api/v1") -> None:
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        self._client = client
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "finnhub"

    def is_available(self) -> bool:
        return self._client is not None or bool(self.api_key)

    def get_news(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        if self._client is not None:
            rows = self._client.company_news(symbol, _from=start.isoformat(), to=end.isoformat())
        else:
            rows = self._get("company-news", {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()})
        return [self._annotate(row, "company-news") for row in rows]

    def get_sentiment(self, symbol: str) -> list[dict[str, Any]]:
        if self._client is not None:
            payload = self._client.news_sentiment(symbol)
        else:
            payload = self._get("news-sentiment", {"symbol": symbol})
        rows = payload if isinstance(payload, list) else [payload]
        return [self._annotate(row, "news-sentiment") for row in rows]

    def _get(self, endpoint: str, params: dict[str, str]) -> Any:
        if not self.api_key:
            raise FinnhubUnavailableError("FINNHUB_API_KEY is required for live Finnhub calls")
        query = urlencode({**params, "token": self.api_key})
        with urlopen(f"{self.base_url}/{endpoint}?{query}", timeout=20) as response:  # nosec B310 - explicit live adapter
            return json.loads(response.read().decode("utf-8"))

    def _annotate(self, row: dict[str, Any], endpoint: str) -> dict[str, Any]:
        data = dict(row)
        data.setdefault("source", f"finnhub:{endpoint}")
        data.setdefault("provider", "finnhub")
        data.setdefault("provider_call", endpoint)
        return data
