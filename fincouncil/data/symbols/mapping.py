"""Bidirectional symbol mapping — canonical ↔ provider-specific formats.

This is an independent clean-room implementation for T1.2 cross-check.
It does NOT import or reference worker-2's code.

Canonical format: ``{exchange_code}:{local_ticker}``
    Examples: ``US:AAPL``, ``JP:7011``, ``TH:PTT``, ``HK:00700``, ``SH:600519``

Provider formats:
    Yahoo Finance: bare ticker (US), or ticker + suffix (e.g. ``7011.T``, ``PTT.BK``)

Design choices (independent from worker-2):
  - Exchange codes are short uppercase strings, NOT MIC codes.
  - Local ticker is the exchange-native identifier WITHOUT provider suffix.
  - Resolution is deterministic: given (exchange_code, local_ticker) → exactly
    one provider symbol, and vice versa.
  - Zero-padding is preserved: HK ``00700`` stays ``00700`` in canonical form
    even though Yahoo uses ``0700.HK`` ( Yahoo strips leading zeros).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .exchange import ExchangeInfo, REGISTRY


# Pattern for canonical symbols: EXCHANGE:LOCAL_TICKER
_CANONICAL_RE = re.compile(r"^([A-Za-z]{2,4}):([A-Za-z0-9]+)$")

# Pattern for Yahoo-style symbols with suffix: TICKER.SUFFIX
_YAHOO_SUFFIX_RE = re.compile(
    r"^(.+?)\.([A-Za-z]{1,3})$"
)

# Known Yahoo suffix → exchange code mapping (reverse of exchange registry)
_YAHOO_SUFFIX_MAP: dict[str, str] = {}


def _build_yahoo_suffix_map() -> dict[str, str]:
    """Build reverse mapping from Yahoo suffix → exchange code."""
    mapping: dict[str, str] = {}
    for ex in REGISTRY.all_exchanges:
        if ex.yahoo_suffix:
            # yahoo_suffix is like ".T" → strip the dot for lookup
            suffix_key = ex.yahoo_suffix.lstrip(".")
            mapping[suffix_key] = ex.code
    return mapping


# Initialize on module load
_YAHOO_SUFFIX_MAP = _build_yahoo_suffix_map()


@dataclass(frozen=True)
class CanonicalSymbol:
    """Parsed canonical symbol with resolved exchange metadata."""

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
        # Yahoo Finance strips leading zeros from HK tickers: 00700 → 0700
        if self.exchange.code == "HK":
            ticker = ticker.lstrip("0") or ticker  # keep at least one char
        return f"{ticker}{suffix}"

    def __str__(self) -> str:
        return f"{self.exchange_code}:{self.local_ticker}"


def parse_canonical(symbol: str) -> Optional[CanonicalSymbol]:
    """Parse a canonical ``EXCHANGE:TICKER`` string.

    Returns ``None`` if the format is invalid or the exchange code is unknown.
    """
    m = _CANONICAL_RE.match(symbol.strip())
    if not m:
        return None
    code = m.group(1).upper()
    ticker = m.group(2).upper()
    ex = REGISTRY.resolve(code)
    if ex is None:
        return None
    return CanonicalSymbol(
        exchange_code=ex.code,
        local_ticker=ticker,
        exchange=ex,
    )


def from_yahoo(yahoo_symbol: str) -> Optional[CanonicalSymbol]:
    """Convert a Yahoo Finance ticker to canonical form.

    Handles:
      - Bare US tickers: ``AAPL`` → ``US:AAPL``
      - Suffixed tickers: ``7011.T`` → ``JP:7011``, ``PTT.BK`` → ``TH:PTT``
      - HK with stripped zeros: ``0700.HK`` → ``HK:00700``

    Returns ``None`` if the suffix is unknown or format is unexpected.
    """
    symbol = yahoo_symbol.strip()

    # Check for suffix pattern
    m = _YAHOO_SUFFIX_RE.match(symbol)
    if m:
        ticker_part = m.group(1).upper()
        suffix = m.group(2).upper()
        code = _YAHOO_SUFFIX_MAP.get(suffix)
        if code is None:
            return None
        ex = REGISTRY.by_code(code)
        if ex is None:
            return None
        # Re-pad HK tickers: Yahoo uses 0700 but canonical is 00700 (5 digits)
        if code == "HK" and len(ticker_part) < 5:
            ticker_part = ticker_part.zfill(5)
        return CanonicalSymbol(
            exchange_code=code,
            local_ticker=ticker_part,
            exchange=ex,
        )

    # No suffix → assume US market
    ex = REGISTRY.by_code("US")
    if ex is None:
        return None
    return CanonicalSymbol(
        exchange_code="US",
        local_ticker=symbol.upper(),
        exchange=ex,
    )


def to_yahoo(symbol: str) -> Optional[str]:
    """Convert a canonical symbol string to Yahoo Finance format.

    Convenience wrapper: ``to_yahoo("JP:7011")`` → ``"7011.T"``
    """
    parsed = parse_canonical(symbol)
    if parsed is None:
        return None
    return parsed.to_yahoo()


def roundtrip_yahoo(canonical: str) -> Optional[str]:
    """Round-trip: canonical → Yahoo → canonical.

    Returns the canonical string produced by converting to Yahoo and back.
    ``None`` means the round-trip failed (unknown exchange/suffix).
    """
    parsed = parse_canonical(canonical)
    if parsed is None:
        return None
    yahoo_sym = parsed.to_yahoo()
    back = from_yahoo(yahoo_sym)
    if back is None:
        return None
    return str(back)
