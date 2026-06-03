"""Swap-in shim for TradingAgents data layer.

This module provides vendor implementations that redirect TradingAgents
data calls to the FinCouncil data layer via MCP tools.

Usage: Register "fincouncil" as a vendor in TradingAgents interface.py
"""

from fincouncil.data.swap.shim import (
    get_stock_data,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_global_news,
    get_insider_transactions,
    get_stock_stats_indicators_window,
)

__all__ = [
    "get_stock_data",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_news",
    "get_global_news",
    "get_insider_transactions",
    "get_stock_stats_indicators_window",
]
