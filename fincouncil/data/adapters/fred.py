"""Optional FRED adapter for free-tier macro observations."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


class FREDAdapterError(RuntimeError):
    pass


class FREDUnavailableError(FREDAdapterError):
    pass


class FREDAdapter:
    def __init__(self, *, api_key: str | None = None, client: Any | None = None, base_url: str = "https://api.stlouisfed.org/fred") -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self._client = client
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "fred"

    def is_available(self) -> bool:
        return self._client is not None or bool(self.api_key)

    def get_macro(self, series_id: str, **params: Any) -> list[dict[str, Any]]:
        if self._client is not None:
            rows = self._client.series_observations(series_id, **params)
        else:
            rows = self._get("series/observations", {"series_id": series_id, **{k: str(v) for k, v in params.items() if v is not None}}).get("observations", [])
        return [self._annotate(row, series_id) for row in rows]

    def _get(self, endpoint: str, params: dict[str, str]) -> Any:
        if not self.api_key:
            raise FREDUnavailableError("FRED_API_KEY is required for live FRED calls")
        query = urlencode({**params, "api_key": self.api_key, "file_type": "json"})
        with urlopen(f"{self.base_url}/{endpoint}?{query}", timeout=20) as response:  # nosec B310 - explicit live adapter
            return json.loads(response.read().decode("utf-8"))

    def _annotate(self, row: dict[str, Any], series_id: str) -> dict[str, Any]:
        data = dict(row)
        data.setdefault("source", "fred:series_observations")
        data.setdefault("provider", "fred")
        data.setdefault("series_id", series_id)
        return data
