from __future__ import annotations

import json
from pathlib import Path

import pytest

from fincouncil.data.symbols import (
    SymbolMappingError,
    canonical_to_provider,
    canonicalize_symbol,
    provider_to_canonical,
    supported_exchanges,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "symbol_mapping_cases.json"


def _fixture_cases() -> list[dict[str, str]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _fixture_cases())
def test_canonical_to_provider_fixture_cases(case: dict[str, str]) -> None:
    assert canonical_to_provider(case["canonical"]) == case["provider"]


@pytest.mark.parametrize("case", _fixture_cases())
def test_provider_to_canonical_fixture_cases(case: dict[str, str]) -> None:
    assert provider_to_canonical(case["provider"]) == case["canonical"]


@pytest.mark.parametrize("case", _fixture_cases())
def test_fixture_cases_round_trip(case: dict[str, str]) -> None:
    canonical = case["canonical"]
    assert provider_to_canonical(canonical_to_provider(canonical)) == canonicalize_symbol(canonical)


def test_accepts_exchange_aliases_and_normalizes_case() -> None:
    assert canonicalize_symbol("nasdaq:aapl") == "US:AAPL"
    assert canonical_to_provider("jp:7011") == "7011.T"
    assert canonical_to_provider("th:ptt") == "PTT.BK"
    assert canonical_to_provider("hk:700") == "00700.HK"
    assert canonical_to_provider("sh:600519") == "600519.SS"
    assert canonical_to_provider("sz:000001") == "000001.SZ"


def test_plain_provider_symbol_defaults_to_us() -> None:
    assert provider_to_canonical(" aapl ") == "US:AAPL"


def test_supported_exchanges_are_canonical_codes_only() -> None:
    assert supported_exchanges() == ("US", "TSE", "SET", "HKEX", "SSE", "SZSE")


@pytest.mark.parametrize(
    "symbol",
    ["", "AAPL", "US:", ":AAPL", "UNKNOWN:AAPL", "HKEX:123456", "US:AA PL"],
)
def test_invalid_canonical_symbols_raise(symbol: str) -> None:
    with pytest.raises(SymbolMappingError):
        canonical_to_provider(symbol)


@pytest.mark.parametrize("symbol", [".HK", "   ", "AA PL"])
def test_invalid_provider_symbols_raise(symbol: str) -> None:
    with pytest.raises(SymbolMappingError):
        provider_to_canonical(symbol)
