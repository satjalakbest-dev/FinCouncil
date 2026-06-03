"""Tests for FinCouncil symbol mapping — independent T1.2 cross-check.

These tests validate the bidirectional mapping between canonical
``{exchange}:{ticker}`` format and Yahoo Finance provider format
using the fixture table from ``fincouncil.data.symbols.fixtures``.

Run: ``python -m pytest tests/symbols/ -v``
"""

from __future__ import annotations

import pytest

from fincouncil.data.symbols.exchange import REGISTRY
from fincouncil.data.symbols.mapping import (
    CanonicalSymbol,
    from_yahoo,
    parse_canonical,
    roundtrip_yahoo,
    to_yahoo,
)
from fincouncil.data.symbols.fixtures import FIXTURES, SymbolFixture


# ═══════════════════════════════════════════════════════════════════════
# Exchange registry tests
# ═══════════════════════════════════════════════════════════════════════

class TestExchangeRegistry:
    """Validate the exchange metadata registry."""

    def test_all_six_markets_registered(self):
        """US, JP, TH, HK, SH, SZ must all be present."""
        codes = {ex.code for ex in REGISTRY.all_exchanges}
        assert codes == {"US", "JP", "TH", "HK", "SH", "SZ"}

    def test_lookup_by_code(self):
        assert REGISTRY.by_code("US") is not None
        assert REGISTRY.by_code("JP") is not None
        assert REGISTRY.by_code("TH") is not None
        assert REGISTRY.by_code("HK") is not None
        assert REGISTRY.by_code("SH") is not None
        assert REGISTRY.by_code("SZ") is not None

    def test_lookup_by_mic(self):
        assert REGISTRY.by_mic("XNAS") is not None
        assert REGISTRY.by_mic("XTKS") is not None
        assert REGISTRY.by_mic("XBKK") is not None
        assert REGISTRY.by_mic("XHKG") is not None
        assert REGISTRY.by_mic("XSHG") is not None
        assert REGISTRY.by_mic("XSHE") is not None

    def test_lookup_by_alias(self):
        """Common aliases like SET, TSE, HKEX resolve correctly."""
        assert REGISTRY.by_alias("SET") is not None
        assert REGISTRY.by_alias("TSE") is not None
        assert REGISTRY.by_alias("HKEX") is not None
        assert REGISTRY.by_alias("SSE") is not None
        assert REGISTRY.by_alias("SZSE") is not None

    def test_unknown_returns_none(self):
        assert REGISTRY.by_code("XX") is None
        assert REGISTRY.by_mic("XXXX") is None
        assert REGISTRY.by_alias("UNKNOWN") is None

    def test_currency_per_market(self):
        """Each market has a distinct, correct currency."""
        expected = {
            "US": "USD", "JP": "JPY", "TH": "THB",
            "HK": "HKD", "SH": "CNY", "SZ": "CNY",
        }
        for code, cur in expected.items():
            ex = REGISTRY.by_code(code)
            assert ex is not None, f"Missing exchange {code}"
            assert ex.currency == cur, f"{code}: expected {cur}, got {ex.currency}"

    def test_yahoo_suffix_per_market(self):
        """Yahoo suffixes match the sprint spec."""
        expected = {
            "US": "", "JP": ".T", "TH": ".BK",
            "HK": ".HK", "SH": ".SS", "SZ": ".SZ",
        }
        for code, suffix in expected.items():
            ex = REGISTRY.by_code(code)
            assert ex is not None
            assert ex.yahoo_suffix == suffix, f"{code}: expected {suffix!r}, got {ex.yahoo_suffix!r}"


# ═══════════════════════════════════════════════════════════════════════
# Canonical parsing tests
# ═══════════════════════════════════════════════════════════════════════

class TestParseCanonical:
    """Validate canonical symbol parsing."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_parse_fixture_canonical(self, fixture: SymbolFixture):
        parsed = parse_canonical(fixture.canonical)
        assert parsed is not None, f"Failed to parse {fixture.canonical}"
        assert parsed.exchange_code == fixture.exchange_code
        assert parsed.local_ticker == fixture.local_ticker

    def test_parse_case_insensitive(self):
        parsed = parse_canonical("us:aapl")
        assert parsed is not None
        assert parsed.exchange_code == "US"
        assert parsed.local_ticker == "AAPL"

    def test_parse_with_whitespace(self):
        parsed = parse_canonical("  JP:7011  ")
        assert parsed is not None
        assert parsed.exchange_code == "JP"
        assert parsed.local_ticker == "7011"

    def test_parse_invalid_format(self):
        assert parse_canonical("") is None
        assert parse_canonical("AAPL") is None        # missing exchange
        assert parse_canonical(":AAPL") is None        # missing exchange code
        assert parse_canonical("US:") is None          # missing ticker
        assert parse_canonical("US:AAPL:extra") is None  # too many parts

    def test_parse_unknown_exchange(self):
        assert parse_canonical("XX:AAPL") is None


# ═══════════════════════════════════════════════════════════════════════
# Yahoo conversion tests (canonical → Yahoo)
# ═══════════════════════════════════════════════════════════════════════

class TestToYahoo:
    """Validate canonical → Yahoo Finance conversion."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_to_yahoo_fixture(self, fixture: SymbolFixture):
        result = to_yahoo(fixture.canonical)
        assert result == fixture.yahoo, (
            f"{fixture.canonical}: expected Yahoo {fixture.yahoo!r}, got {result!r}"
        )

    def test_to_yahoo_invalid(self):
        assert to_yahoo("INVALID") is None
        assert to_yahoo("XX:AAPL") is None


# ═══════════════════════════════════════════════════════════════════════
# Yahoo reverse tests (Yahoo → canonical)
# ═══════════════════════════════════════════════════════════════════════

class TestFromYahoo:
    """Validate Yahoo Finance → canonical conversion."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_from_yahoo_fixture(self, fixture: SymbolFixture):
        result = from_yahoo(fixture.yahoo)
        assert result is not None, f"from_yahoo({fixture.yahoo!r}) returned None"
        assert str(result) == fixture.canonical, (
            f"from_yahoo({fixture.yahoo!r}): expected {fixture.canonical!r}, got {str(result)!r}"
        )

    def test_from_yahoo_bare_us_ticker(self):
        """Bare ticker without suffix defaults to US."""
        result = from_yahoo("AAPL")
        assert result is not None
        assert str(result) == "US:AAPL"

    def test_from_yahoo_unknown_suffix(self):
        assert from_yahoo("FOO.ZZ") is None


# ═══════════════════════════════════════════════════════════════════════
# Round-trip tests (canonical → Yahoo → canonical)
# ═══════════════════════════════════════════════════════════════════════

class TestRoundtrip:
    """Round-trip must be identity: canonical → Yahoo → canonical."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_roundtrip_yahoo(self, fixture: SymbolFixture):
        result = roundtrip_yahoo(fixture.canonical)
        assert result == fixture.canonical, (
            f"Round-trip failed: {fixture.canonical} → Yahoo → {result!r}"
        )

    def test_roundtrip_invalid(self):
        assert roundtrip_yahoo("INVALID") is None


# ═══════════════════════════════════════════════════════════════════════
# Currency / metadata tests (schema review)
# ═══════════════════════════════════════════════════════════════════════

class TestCurrencyMetadata:
    """Every canonical symbol must carry currency from exchange metadata."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_currency_attached(self, fixture: SymbolFixture):
        parsed = parse_canonical(fixture.canonical)
        assert parsed is not None
        assert parsed.currency == fixture.currency, (
            f"{fixture.canonical}: expected currency {fixture.currency}, got {parsed.currency}"
        )

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_mic_attached(self, fixture: SymbolFixture):
        """Every parsed symbol has a valid ISO 10383 MIC."""
        parsed = parse_canonical(fixture.canonical)
        assert parsed is not None
        assert len(parsed.mic) == 4, f"Invalid MIC: {parsed.mic}"
        assert parsed.mic.startswith("X"), f"MIC should start with X: {parsed.mic}"

    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.canonical)
    def test_country_attached(self, fixture: SymbolFixture):
        """Every parsed symbol has a valid ISO 3166-1 country code."""
        parsed = parse_canonical(fixture.canonical)
        assert parsed is not None
        assert len(parsed.country) == 2, f"Invalid country code: {parsed.country}"


# ═══════════════════════════════════════════════════════════════════════
# Edge case tests
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases that the sprint spec and fixtures highlight."""

    def test_hk_zero_padding_to_yahoo(self):
        """HK 00700 → Yahoo 0700.HK (Yahoo strips one leading zero)."""
        result = to_yahoo("HK:00700")
        assert result == "0700.HK"

    def test_hk_zero_padding_from_yahoo(self):
        """Yahoo 0700.HK → canonical HK:00700 (re-pad to 5 digits)."""
        result = from_yahoo("0700.HK")
        assert result is not None
        assert result.local_ticker == "00700"

    def test_hk_roundtrip_preserves_padding(self):
        """HK:00700 → 0700.HK → HK:00700 (zero-padding preserved)."""
        assert roundtrip_yahoo("HK:00700") == "HK:00700"

    def test_hk_00005_roundtrip(self):
        """HK:00005 → 0005.HK → HK:00005."""
        assert roundtrip_yahoo("HK:00005") == "HK:00005"

    def test_china_shanghai_vs_shenzhen(self):
        """Shanghai (.SS) and Shenzhen (.SZ) must not be confused."""
        sh = to_yahoo("SH:600519")
        sz = to_yahoo("SZ:000858")
        assert sh == "600519.SS"
        assert sz == "000858.SZ"
        assert sh != sz  # different suffixes

    def test_china_roundtrip(self):
        """SH and SZ round-trip correctly."""
        assert roundtrip_yahoo("SH:600519") == "SH:600519"
        assert roundtrip_yahoo("SZ:000858") == "SZ:000858"

    def test_us_no_suffix(self):
        """US tickers have no Yahoo suffix."""
        result = to_yahoo("US:AAPL")
        assert "." not in result
        assert result == "AAPL"
