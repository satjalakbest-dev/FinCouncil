"""Exchange registry — market metadata for symbol mapping.

Each exchange entry carries:
- code: short identifier used in canonical symbols (e.g. "US", "JP", "TH")
- mic: ISO 10383 Market Identifier Code (e.g. "XNAS", "XTKS")
- name: human-readable market name
- currency: ISO 4217 default currency for this market
- yahoo_suffix: Yahoo Finance ticker suffix (empty string for US)
- country: ISO 3166-1 alpha-2 country code
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional


@dataclass(frozen=True)
class ExchangeInfo:
    """Immutable metadata for a single exchange/market."""

    code: str            # short code: "US", "JP", "TH", "HK", "SH", "SZ"
    mic: str             # ISO 10383 MIC: "XNAS", "XTKS", "XBKK", "XHKG", "XSHG", "XSHE"
    name: str            # human-readable: "NASDAQ/NYSE", "Tokyo Stock Exchange"
    country: str         # ISO 3166-1 alpha-2: "US", "JP", "TH", "HK", "CN"
    currency: str        # ISO 4217: "USD", "JPY", "THB", "HKD", "CNY"
    yahoo_suffix: str    # Yahoo Finance suffix: "", ".T", ".BK", ".HK", ".SS", ".SZ"
    aliases: FrozenSet[str] = field(default_factory=frozenset)

    @property
    def is_china(self) -> bool:
        return self.country == "CN"


# ---------------------------------------------------------------------------
# Registry — every market we cover
# ---------------------------------------------------------------------------
_EXCHANGE_DATA: list[dict] = [
    # US — composite for NASDAQ/NYSE (no single suffix; Yahoo uses bare ticker)
    dict(
        code="US", mic="XNAS", name="NASDAQ/NYSE", country="US",
        currency="USD", yahoo_suffix="",
        aliases=frozenset({"NASDAQ", "NYSE", "US_EQ", "XNYS"}),
    ),
    # Japan — Tokyo Stock Exchange
    dict(
        code="JP", mic="XTKS", name="Tokyo Stock Exchange", country="JP",
        currency="JPY", yahoo_suffix=".T",
        aliases=frozenset({"TSE", "TYO", "TOKYO"}),
    ),
    # Thailand — Stock Exchange of Thailand
    dict(
        code="TH", mic="XBKK", name="Stock Exchange of Thailand", country="TH",
        currency="THB", yahoo_suffix=".BK",
        aliases=frozenset({"SET", "BKK"}),
    ),
    # Hong Kong — Hong Kong Stock Exchange
    dict(
        code="HK", mic="XHKG", name="Hong Kong Stock Exchange", country="HK",
        currency="HKD", yahoo_suffix=".HK",
        aliases=frozenset({"HKEX", "HKE"}),
    ),
    # China Shanghai — Shanghai Stock Exchange
    dict(
        code="SH", mic="XSHG", name="Shanghai Stock Exchange", country="CN",
        currency="CNY", yahoo_suffix=".SS",
        aliases=frozenset({"SSE", "SHANGHAI"}),
    ),
    # China Shenzhen — Shenzhen Stock Exchange
    dict(
        code="SZ", mic="XSHE", name="Shenzhen Stock Exchange", country="CN",
        currency="CNY", yahoo_suffix=".SZ",
        aliases=frozenset({"SZSE", "SHENZHEN"}),
    ),
]


class ExchangeRegistry:
    """Lookup exchange metadata by code, MIC, or alias."""

    def __init__(self) -> None:
        self._by_code: Dict[str, ExchangeInfo] = {}
        self._by_mic: Dict[str, ExchangeInfo] = {}
        self._by_alias: Dict[str, ExchangeInfo] = {}
        for entry in _EXCHANGE_DATA:
            info = ExchangeInfo(**entry)
            self._by_code[info.code] = info
            self._by_mic[info.mic] = info
            for alias in info.aliases:
                self._by_alias[alias] = info

    def by_code(self, code: str) -> Optional[ExchangeInfo]:
        """Look up by canonical short code (e.g. ``"JP"``)."""
        return self._by_code.get(code.upper())

    def by_mic(self, mic: str) -> Optional[ExchangeInfo]:
        """Look up by ISO 10383 MIC (e.g. ``"XTKS"``)."""
        return self._by_mic.get(mic.upper())

    def by_alias(self, alias: str) -> Optional[ExchangeInfo]:
        """Look up by common alias (e.g. ``"SET"``, ``"TSE"``)."""
        return self._by_alias.get(alias.upper())

    def resolve(self, key: str) -> Optional[ExchangeInfo]:
        """Try code → MIC → alias resolution in order."""
        return self.by_code(key) or self.by_mic(key) or self.by_alias(key)

    @property
    def all_exchanges(self) -> list[ExchangeInfo]:
        return list(self._by_code.values())


# Module-level singleton
REGISTRY = ExchangeRegistry()
