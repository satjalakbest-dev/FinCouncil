"""FinCouncil symbol mapping — canonical {exchange}:{ticker} ↔ provider suffixes.

This module provides bidirectional mapping between FinCouncil's canonical
symbol format and provider-specific ticker conventions (Yahoo Finance, OpenBB,
etc.). It is an independent clean-room implementation for T1.2 cross-check.

Canonical format: ``{exchange_code}:{local_ticker}``
    e.g. ``US:AAPL``, ``JP:7011``, ``TH:PTT``, ``HK:00700``, ``SH:600519``

Exchange codes are short, memorable identifiers derived from market names,
NOT provider-specific suffixes. Each provider adapter translates between
canonical form and its own convention.
"""
