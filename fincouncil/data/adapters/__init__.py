"""Adapter interfaces for data providers.

Every data source (OpenBB, yfinance, Alpha Vantage, etc.) implements
the ``BaseAdapter`` interface.  The normalizer converts raw adapter
output into canonical ``PriceRecord`` / ``FundamentalsRecord`` objects.
"""
