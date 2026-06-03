"""Canonical symbol mapping for FinCouncil data providers.

The canonical FinCouncil convention is ``{exchange}:{ticker}`` where the
exchange is an internal market code and the ticker is the exchange-local symbol.
Provider symbols are currently normalized for Yahoo/OpenBB-style suffixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ExchangeRule:
    """Mapping rule between a canonical exchange code and provider suffix."""

    exchange_code: str
    local_ticker: str
    exchange: ExchangeInfo

    @property
    def currency(self) -> str:
        return self.exchange.currency

    @property
    def mic(self) -> str:
        return self.exchange.mic

    @property
    def country(self) -> str:
        return self.exchange.country

    def to_yahoo(self) -> str:
        """Convert to Yahoo Finance ticker format."""
        suffix = self.exchange.yahoo_suffix
        ticker = self.local_ticker
        # Yahoo Finance uses 4-digit HK tickers: canonical 00700 → Yahoo 0700
        if self.exchange.code == "HK":
            ticker = str(int(ticker)).zfill(4)
        return f"{ticker}{suffix}"

    def __str__(self) -> str:
        return f"{self.exchange_code}:{self.local_ticker}"


_RULES: Final[tuple[ExchangeRule, ...]] = (
    ExchangeRule("US", "", aliases=("NASDAQ", "NYSE", "AMEX")),
    ExchangeRule("TSE", ".T", aliases=("JP", "JPX", "TYO", "TOKYO")),
    ExchangeRule("SET", ".BK", aliases=("TH", "THAI", "BKK")),
    ExchangeRule("HKEX", ".HK", aliases=("HK", "HKG"), pad_width=5),
    ExchangeRule("SSE", ".SS", aliases=("SH", "SHA", "SHANGHAI")),
    ExchangeRule("SZSE", ".SZ", aliases=("SZ", "SHE", "SHENZHEN")),
)

_RULE_BY_EXCHANGE: Final[dict[str, ExchangeRule]] = {
    code: rule
    for rule in _RULES
    for code in (rule.canonical_exchange, *rule.aliases)
}
_RULE_BY_SUFFIX: Final[dict[str, ExchangeRule]] = {
    rule.provider_suffix: rule for rule in _RULES if rule.provider_suffix
}


class SymbolMappingError(ValueError):
    """Raised when a symbol cannot be converted safely."""


def canonicalize_symbol(canonical_symbol: str) -> str:
    """Return a normalized ``{exchange}:{ticker}`` canonical symbol."""

    exchange, ticker = _split_canonical(canonical_symbol)
    rule = _rule_for_exchange(exchange)
    return f"{rule.canonical_exchange}:{_normalize_ticker(ticker, rule)}"


def canonical_to_provider(canonical_symbol: str) -> str:
    """Convert ``{exchange}:{ticker}`` to a provider suffix symbol.

    Examples:
        ``US:AAPL`` -> ``AAPL``
        ``TSE:7011`` -> ``7011.T``
        ``SET:PTT`` -> ``PTT.BK``
        ``HKEX:700`` -> ``00700.HK``
    """

    exchange, ticker = _split_canonical(canonical_symbol)
    rule = _rule_for_exchange(exchange)
    normalized_ticker = _normalize_ticker(ticker, rule)
    return f"{normalized_ticker}{rule.provider_suffix}"


def provider_to_canonical(provider_symbol: str, *, default_exchange: str = "US") -> str:
    """Convert a provider suffix symbol to canonical ``{exchange}:{ticker}``.

    Provider symbols without a known suffix are treated as ``default_exchange``;
    the default is ``US`` for plain Yahoo/OpenBB tickers such as ``AAPL``.
    """

    symbol = _clean_symbol(provider_symbol, field_name="provider_symbol")
    upper_symbol = symbol.upper()

    for suffix, rule in sorted(_RULE_BY_SUFFIX.items(), key=lambda item: len(item[0]), reverse=True):
        if upper_symbol.endswith(suffix):
            raw_ticker = upper_symbol[: -len(suffix)]
            if not raw_ticker:
                raise SymbolMappingError(f"provider symbol {provider_symbol!r} has no ticker before suffix")
            return f"{rule.canonical_exchange}:{_normalize_ticker(raw_ticker, rule)}"

    rule = _rule_for_exchange(default_exchange)
    return f"{rule.canonical_exchange}:{_normalize_ticker(upper_symbol, rule)}"


def supported_exchanges() -> tuple[str, ...]:
    """Return canonical exchange codes supported by the mapper."""

    return tuple(rule.canonical_exchange for rule in _RULES)


def _split_canonical(canonical_symbol: str) -> tuple[str, str]:
    symbol = _clean_symbol(canonical_symbol, field_name="canonical_symbol")
    if ":" not in symbol:
        raise SymbolMappingError(
            f"canonical symbol {canonical_symbol!r} must use the '{{exchange}}:{{ticker}}' format"
        )
    exchange, ticker = symbol.split(":", 1)
    if not exchange or not ticker:
        raise SymbolMappingError(f"canonical symbol {canonical_symbol!r} must include exchange and ticker")
    return exchange.upper(), ticker.upper()


def _rule_for_exchange(exchange: str) -> ExchangeRule:
    try:
        return _RULE_BY_EXCHANGE[exchange.upper()]
    except KeyError as exc:
        supported = ", ".join(supported_exchanges())
        raise SymbolMappingError(f"unsupported exchange {exchange!r}; supported exchanges: {supported}") from exc


def _normalize_ticker(ticker: str, rule: ExchangeRule) -> str:
    cleaned = _clean_symbol(ticker, field_name="ticker").upper()
    if ":" in cleaned:
        raise SymbolMappingError(f"ticker {ticker!r} must not contain ':'")
    if rule.pad_width is not None and cleaned.isdigit():
        if len(cleaned) > rule.pad_width:
            raise SymbolMappingError(
                f"ticker {ticker!r} exceeds {rule.pad_width} digits for {rule.canonical_exchange}"
            )
        return cleaned.zfill(rule.pad_width)
    return cleaned


def _clean_symbol(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise SymbolMappingError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise SymbolMappingError(f"{field_name} must not be empty")
    if any(char.isspace() for char in cleaned):
        raise SymbolMappingError(f"{field_name} must not contain whitespace")
    return cleaned
