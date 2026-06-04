"""Paid Tushare hook stub for explicit Tier A gap reporting."""

from __future__ import annotations


class PaidProviderNotEnabledError(RuntimeError):
    """Raised when a paid provider hook is called without enablement."""


class TushareAdapter:
    @property
    def name(self) -> str:
        return "tushare"

    def is_available(self) -> bool:
        return False

    def get_price(self, *args, **kwargs):
        raise PaidProviderNotEnabledError("Tushare is paid/not enabled in Tier A")

    def get_fundamentals(self, *args, **kwargs):
        raise PaidProviderNotEnabledError("Tushare fundamentals are paid/not enabled in Tier A")
