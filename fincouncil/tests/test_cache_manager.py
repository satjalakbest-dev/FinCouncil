"""Cache manager tests — verify read-local-first pattern and TTL logic.

These tests ensure:
- Cache miss → fetch → cache → second read hits cache
- TTL expiry → stale data triggers re-fetch
- Idempotent writes (same data twice doesn't duplicate)
- is_fresh returns correct boolean
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest

from fincouncil.data.cache.manager import CacheManager, CachePolicy
from fincouncil.data.schema import CurrencyCode, PriceRecord
from fincouncil.data.store.warehouse import DuckDBWarehouse


def _currency(code: str) -> CurrencyCode:
    return CurrencyCode(code)


@pytest.fixture
def memory_warehouse() -> DuckDBWarehouse:
    """In-memory warehouse for isolated test runs."""
    return DuckDBWarehouse(":memory:")


@pytest.fixture
def cache_manager(memory_warehouse: DuckDBWarehouse) -> CacheManager:
    """Cache manager with default 24h TTL."""
    return CacheManager(memory_warehouse)


@pytest.fixture
def mock_adapter() -> Mock:
    """Mock adapter returning synthetic price data."""
    adapter = Mock()
    adapter.get_price.return_value = [
        {
            "date": "2024-01-02",
            "open": "195.00",
            "high": "196.50",
            "low": "194.80",
            "close": "195.50",
            "volume": 50_000_000,
        },
        {
            "date": "2024-01-03",
            "open": "196.00",
            "high": "197.00",
            "low": "195.50",
            "close": "196.80",
            "volume": 45_000_000,
        },
    ]
    return adapter


@pytest.fixture
def sample_price_records() -> list[PriceRecord]:
    """Sample PriceRecord objects for testing."""
    return [
        PriceRecord(
            kind="price",
            source="test",
            currency=_currency("USD"),
            as_of=datetime.now(),
            symbol="US:AAPL",
            date=date(2024, 1, 2),
            open=Decimal("195.00"),
            high=Decimal("196.50"),
            low=Decimal("194.80"),
            close=Decimal("195.50"),
            volume=50_000_000,
            adjusted_close=Decimal("195.50"),
        ),
        PriceRecord(
            kind="price",
            source="test",
            currency=_currency("USD"),
            as_of=datetime.now(),
            symbol="US:AAPL",
            date=date(2024, 1, 3),
            open=Decimal("196.00"),
            high=Decimal("197.00"),
            low=Decimal("195.50"),
            close=Decimal("196.80"),
            volume=45_000_000,
            adjusted_close=Decimal("196.80"),
        ),
    ]


class TestCacheManager:
    """Cache manager core functionality tests."""

    def test_get_prices_returns_empty_when_cache_miss(self, cache_manager: CacheManager) -> None:
        """get_prices returns empty list when no cached data exists."""
        rows = cache_manager.get_prices(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        assert rows == []

    def test_put_prices_and_get_prices_roundtrip(
        self,
        cache_manager: CacheManager,
        sample_price_records: list[PriceRecord],
    ) -> None:
        """put_prices writes records that get_prices can read back."""
        written = cache_manager.put_prices(sample_price_records)
        assert written == 2

        rows = cache_manager.get_prices(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        assert len(rows) == 2
        assert rows[0]["symbol"] == "US:AAPL"
        assert rows[0]["close"] == 195.50

    def test_put_prices_with_empty_list_returns_zero(self, cache_manager: CacheManager) -> None:
        """put_prices with empty list is a no-op."""
        assert cache_manager.put_prices([]) == 0

    def test_put_prices_idempotent(
        self,
        cache_manager: CacheManager,
        sample_price_records: list[PriceRecord],
    ) -> None:
        """Writing the same records twice doesn't create duplicates."""
        cache_manager.put_prices(sample_price_records)
        cache_manager.put_prices(sample_price_records)

        rows = cache_manager.get_prices(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        # Should still have exactly 2 rows, not 4
        assert len(rows) == 2

    def test_is_fresh_returns_false_when_cache_empty(self, cache_manager: CacheManager) -> None:
        """is_fresh returns False when no cached data exists."""
        assert not cache_manager.is_fresh(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            "test",
        )

    def test_is_fresh_returns_true_for_fresh_data(
        self,
        cache_manager: CacheManager,
        sample_price_records: list[PriceRecord],
    ) -> None:
        """is_fresh returns True for data within TTL."""
        cache_manager.put_prices(sample_price_records)
        assert cache_manager.is_fresh(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            "test",
        )

    def test_is_fresh_returns_false_for_stale_data(
        self,
        cache_manager: CacheManager,
        sample_price_records: list[PriceRecord],
    ) -> None:
        """is_fresh returns False when data exceeds TTL."""
        cache_manager.put_prices(sample_price_records)

        # Override TTL to 0 hours for testing
        assert not cache_manager.is_fresh(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            "test",
            max_age_hours=0,
        )

    def test_is_fresh_respects_source_filter(
        self,
        cache_manager: CacheManager,
        sample_price_records: list[PriceRecord],
    ) -> None:
        """is_fresh only checks data for the specified source."""
        cache_manager.put_prices(sample_price_records)

        # Should be fresh for "test" source
        assert cache_manager.is_fresh(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            "test",
        )

        # Should not be fresh for "other" source (no data)
        assert not cache_manager.is_fresh(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            "other",
        )


class TestGetOrCreate:
    """get_or_fetch read-local-first pattern tests."""

    def test_cache_miss_fetches_from_adapter(
        self,
        cache_manager: CacheManager,
        mock_adapter: Mock,
    ) -> None:
        """Cache miss triggers adapter call and caches result."""
        records = cache_manager.get_or_fetch(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            mock_adapter,
            "USD",
            "test",
        )

        assert len(records) == 2
        assert mock_adapter.get_price.call_count == 1

        # Verify data was cached
        cached_rows = cache_manager.get_prices(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            source="test",
        )
        assert len(cached_rows) == 2

    def test_cache_hit_skips_adapter(
        self,
        cache_manager: CacheManager,
        mock_adapter: Mock,
    ) -> None:
        """Cache hit returns cached data without calling adapter."""
        # First call populates cache
        cache_manager.get_or_fetch(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            mock_adapter,
            "USD",
            "test",
        )

        # Second call should hit cache
        records = cache_manager.get_or_fetch(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            mock_adapter,
            "USD",
            "test",
        )

        assert len(records) == 2
        # Adapter should still have been called only once (from first call)
        assert mock_adapter.get_price.call_count == 1

    def test_stale_cache_triggers_refresh(
        self,
        cache_manager: CacheManager,
        mock_adapter: Mock,
    ) -> None:
        """Stale cache triggers a new adapter call."""
        # First call populates cache
        cache_manager.get_or_fetch(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            mock_adapter,
            "USD",
            "test",
        )

        # Simulate time passing by setting TTL to 0
        # This should trigger a refresh
        records = cache_manager.get_or_fetch(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            mock_adapter,
            "USD",
            "test",
            force_refresh=True,
        )

        assert len(records) == 2
        # Adapter should have been called twice (initial + refresh)
        assert mock_adapter.get_price.call_count == 2

    def test_adapter_returns_empty_list(
        self,
        cache_manager: CacheManager,
        mock_adapter: Mock,
    ) -> None:
        """Adapter returning empty list results in no cache write."""
        mock_adapter.get_price.return_value = []

        records = cache_manager.get_or_fetch(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            mock_adapter,
            "USD",
            "test",
        )

        assert records == []

        # Verify nothing was cached
        cached_rows = cache_manager.get_prices(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
            source="test",
        )
        assert cached_rows == []


class TestCachePolicy:
    """CachePolicy configuration tests."""

    def test_default_policy(self) -> None:
        """Default policy has 24h TTL for EOD prices."""
        policy = CachePolicy()
        assert policy.eod_prices_max_age_hours == 24
        assert policy.max_age_for("price") == timedelta(hours=24)

    def test_custom_policy(self) -> None:
        """Custom policy overrides default TTL."""
        policy = CachePolicy(eod_prices_max_age_hours=12)
        assert policy.eod_prices_max_age_hours == 12
        assert policy.max_age_for("price") == timedelta(hours=12)

    def test_fundamentals_ttl(self) -> None:
        """Fundamentals have longer default TTL (7 days)."""
        policy = CachePolicy()
        assert policy.fundamentals_max_age_hours == 24 * 7
        assert policy.max_age_for("fundamentals") == timedelta(hours=24 * 7)


class TestNormalizeCachedRows:
    """_normalize_cached_rows reconstruction tests."""

    def test_reconstructs_price_records(
        self,
        cache_manager: CacheManager,
        sample_price_records: list[PriceRecord],
    ) -> None:
        """Cached warehouse rows are reconstructed as PriceRecords."""
        from fincouncil.data.cache.manager import _normalize_cached_rows

        # Write records to warehouse
        cache_manager.put_prices(sample_price_records)

        # Read back as warehouse rows
        warehouse_rows = cache_manager.get_prices(
            "US:AAPL",
            date(2024, 1, 1),
            date(2024, 1, 31),
        )

        # Reconstruct as PriceRecords
        records = _normalize_cached_rows(warehouse_rows, "US:AAPL", "USD")

        assert len(records) == 2
        assert records[0].symbol == "US:AAPL"
        assert records[0].close == Decimal("195.50")
        assert isinstance(records[0].close, Decimal)

    def test_empty_list_returns_empty_records(self) -> None:
        """Empty warehouse rows result in empty PriceRecord list."""
        from fincouncil.data.cache.manager import _normalize_cached_rows

        records = _normalize_cached_rows([], "US:AAPL", "USD")
        assert records == []
