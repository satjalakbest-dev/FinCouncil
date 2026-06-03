"""Fixture table for T1.2 symbol mapping cross-check.

These fixtures define the EXPECTED mapping results for a set of representative
tickers across all supported markets. Both worker-2 and worker-5 (this module)
must produce identical results on these fixtures — any discrepancy must be
investigated, not silently accepted.

 Fixture rules:
   - No fabricated financial data — these are only symbol identifiers.
   - Currency is derived from exchange metadata, not hardcoded per ticker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SymbolFixture:
    """A single test case for symbol mapping round-trips."""

    canonical: str       # e.g. "US:AAPL"
    yahoo: str           # e.g. "AAPL" (US), "7011.T" (JP), "PTT.BK" (TH)
    exchange_code: str   # "US", "JP", "TH", "HK", "SH", "SZ"
    local_ticker: str    # "AAPL", "7011", "PTT", "00700", "600519"
    currency: str        # derived from exchange: "USD", "JPY", "THB", "HKD", "CNY"
    description: str     # human label for the test case


FIXTURES: List[SymbolFixture] = [
    # ── US Market ──────────────────────────────────────────────────────
    SymbolFixture(
        canonical="US:AAPL",
        yahoo="AAPL",
        exchange_code="US",
        local_ticker="AAPL",
        currency="USD",
        description="Apple Inc. — NASDAQ",
    ),
    SymbolFixture(
        canonical="US:MSFT",
        yahoo="MSFT",
        exchange_code="US",
        local_ticker="MSFT",
        currency="USD",
        description="Microsoft Corp. — NASDAQ",
    ),
    SymbolFixture(
        canonical="US:GOOGL",
        yahoo="GOOGL",
        exchange_code="US",
        local_ticker="GOOGL",
        currency="USD",
        description="Alphabet Inc. — NASDAQ",
    ),
    # ── Japan (Tokyo Stock Exchange) ───────────────────────────────────
    SymbolFixture(
        canonical="JP:7011",
        yahoo="7011.T",
        exchange_code="JP",
        local_ticker="7011",
        currency="JPY",
        description="Mitsubishi Heavy Industries — TSE",
    ),
    SymbolFixture(
        canonical="JP:7203",
        yahoo="7203.T",
        exchange_code="JP",
        local_ticker="7203",
        currency="JPY",
        description="Toyota Motor Corp. — TSE",
    ),
    SymbolFixture(
        canonical="JP:6758",
        yahoo="6758.T",
        exchange_code="JP",
        local_ticker="6758",
        currency="JPY",
        description="Sony Group Corp. — TSE",
    ),
    # ── Thailand (SET) ─────────────────────────────────────────────────
    SymbolFixture(
        canonical="TH:PTT",
        yahoo="PTT.BK",
        exchange_code="TH",
        local_ticker="PTT",
        currency="THB",
        description="PTT Public Co. Ltd. — SET",
    ),
    SymbolFixture(
        canonical="TH:AOT",
        yahoo="AOT.BK",
        exchange_code="TH",
        local_ticker="AOT",
        currency="THB",
        description="Airports of Thailand — SET",
    ),
    SymbolFixture(
        canonical="TH:CPALL",
        yahoo="CPALL.BK",
        exchange_code="TH",
        local_ticker="CPALL",
        currency="THB",
        description="CP ALL Public Co. Ltd. — SET",
    ),
    # ── Hong Kong (HKEX) ──────────────────────────────────────────────
    SymbolFixture(
        canonical="HK:00700",
        yahoo="0700.HK",
        exchange_code="HK",
        local_ticker="00700",
        currency="HKD",
        description="Tencent Holdings — HKEX (note Yahoo strips leading zero)",
    ),
    SymbolFixture(
        canonical="HK:00005",
        yahoo="0005.HK",
        exchange_code="HK",
        local_ticker="00005",
        currency="HKD",
        description="HSBC Holdings — HKEX",
    ),
    SymbolFixture(
        canonical="HK:00941",
        yahoo="0941.HK",
        exchange_code="HK",
        local_ticker="00941",
        currency="HKD",
        description="China Mobile — HKEX",
    ),
    # ── China Shanghai (SSE) ───────────────────────────────────────────
    SymbolFixture(
        canonical="SH:600519",
        yahoo="600519.SS",
        exchange_code="SH",
        local_ticker="600519",
        currency="CNY",
        description="Kweichow Moutai — Shanghai SE",
    ),
    SymbolFixture(
        canonical="SH:601318",
        yahoo="601318.SS",
        exchange_code="SH",
        local_ticker="601318",
        currency="CNY",
        description="Ping An Insurance — Shanghai SE",
    ),
    # ── China Shenzhen (SZSE) ──────────────────────────────────────────
    SymbolFixture(
        canonical="SZ:000858",
        yahoo="000858.SZ",
        exchange_code="SZ",
        local_ticker="000858",
        currency="CNY",
        description="Wuliangye Yibin — Shenzhen SE",
    ),
    SymbolFixture(
        canonical="SZ:300750",
        yahoo="300750.SZ",
        exchange_code="SZ",
        local_ticker="300750",
        currency="CNY",
        description="CATL (Contemporary Amperex) — Shenzhen SE",
    ),
]
