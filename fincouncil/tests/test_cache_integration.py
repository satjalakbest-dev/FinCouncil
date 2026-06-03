"""Cache integration tests for T1.7 — verify cache behavior.

These tests verify:
1. Repeated requests hit cache (don't call adapter again)
2. Cache writes canonical records
3. Cache freshness checks work correctly
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from fincouncil.data.cache.manager import CacheManager, CachePolicy
from fincouncil.data.schema import CurrencyCode, PriceRecord
from fincouncil.data.store.warehouse import DuckDBWarehouse


class FakeAdapterForCache:
    """Fake adapter that tracks call count."""

    def __init__(self):
        self.call_count = 0
        self.records_to_return = []

    def is_available(self):
        return True

    def get_price(self, symbol, start, end):
        self.call_count += 1
        return self.records_to_return


class TestCacheIntegration:
    """Integration tests for cache manager behavior."""

    def test_cache_manager_initializes_with_warehouse(self):
        """Cache manager should initialize with a warehouse."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)
        assert cache._warehouse is warehouse

    def test_cache_manager_initializes_with_default_policy(self):
        """Cache manager should initialize with default policy if not provided."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)
        assert cache._policy is not None
        assert cache._policy.eod_prices_max_age_hours == 24

    def test_cache_manager_initializes_with_custom_policy(self):
        """Cache manager should accept a custom cache policy."""
        warehouse = DuckDBWarehouse(":memory:")
        policy = CachePolicy(eod_prices_max_age_hours=12)
        cache = CacheManager(warehouse, policy=policy)
        assert cache._policy.eod_prices_max_age_hours == 12

    def test_get_or_fetch_calls_adapter_on_first_request(self):
        """First request should call the adapter."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)
        adapter = FakeAdapterForCache()

        # Setup adapter to return one record
        adapter.records_to_return = [
            {
                "date": "2024-01-02",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 1000000,
                "source": "test",
            }
        ]

        records = cache.get_or_fetch(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            adapter=adapter,
            currency="USD",
            source="test",
        )

        assert adapter.call_count == 1
        assert len(records) == 1

    def test_get_or_fetch_skips_adapter_when_fresh_cache_exists(self):
        """Second request with fresh cache should not call the adapter."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)
        adapter = FakeAdapterForCache()

        # Setup adapter to return one record
        adapter.records_to_return = [
            {
                "date": "2024-01-02",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 1000000,
                "source": "test",
            }
        ]

        # First request
        records1 = cache.get_or_fetch(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            adapter=adapter,
            currency="USD",
            source="test",
        )

        call_count_after_first = adapter.call_count

        # Second request (should hit cache)
        records2 = cache.get_or_fetch(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            adapter=adapter,
            currency="USD",
            source="test",
        )

        # Adapter should not be called again
        assert adapter.call_count == call_count_after_first
        assert len(records2) == 1

    def test_get_or_fetch_calls_adapter_when_force_refresh_true(self):
        """Request with force_refresh=True should call adapter even with cache."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)
        adapter = FakeAdapterForCache()

        # Setup adapter to return one record
        adapter.records_to_return = [
            {
                "date": "2024-01-02",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 1000000,
                "source": "test",
            }
        ]

        # First request
        records1 = cache.get_or_fetch(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            adapter=adapter,
            currency="USD",
            source="test",
        )

        call_count_after_first = adapter.call_count

        # Second request with force_refresh
        records2 = cache.get_or_fetch(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            adapter=adapter,
            currency="USD",
            source="test",
            force_refresh=True,
        )

        # Adapter should be called again
        assert adapter.call_count > call_count_after_first

    def test_put_prices_writes_to_warehouse(self):
        """put_prices should write records to the warehouse."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)

        records = [
            PriceRecord(
                kind="price",
                symbol="US:AAPL",
                date=date(2024, 1, 2),
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("99.0"),
                close=Decimal("104.0"),
                volume=1000000,
                adjusted_close=Decimal("104.0"),
                source="test",
                currency=CurrencyCode("USD"),
                as_of=datetime.now(),
            )
        ]

        count = cache.put_prices(records)
        assert count == 1

    def test_put_prices_with_empty_list_returns_zero(self):
        """put_prices with empty list should return 0."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)

        count = cache.put_prices([])
        assert count == 0

    def test_is_fresh_returns_false_when_no_data(self):
        """is_fresh should return False when no cached data exists."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)

        is_fresh = cache.is_fresh(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            source="test",
        )

        assert is_fresh is False

    def test_is_fresh_returns_true_for_recent_data(self):
        """is_fresh should return True for data within TTL."""
        warehouse = DuckDBWarehouse(":memory:")
        cache = CacheManager(warehouse)

        # Write fresh data
        records = [
            PriceRecord(
                kind="price",
                symbol="US:AAPL",
                date=date(2024, 1, 2),
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("99.0"),
                close=Decimal("104.0"),
                volume=1000000,
                adjusted_close=Decimal("104.0"),
                source="test",
                currency=CurrencyCode("USD"),
                as_of=datetime.now(),
            )
        ]
        cache.put_prices(records)

        is_fresh = cache.is_fresh(
            symbol="US:AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            source="test",
        )

        assert is_fresh is True


class TestCachePolicy:
    """Tests for CachePolicy configuration."""

    def test_default_policy_values(self):
        """Default policy should have expected values."""
        policy = CachePolicy()
        assert policy.default_max_age_hours == 24
        assert policy.eod_prices_max_age_hours == 24
        assert policy.fundamentals_max_age_hours == 24 * 7

    def test_max_age_for_price_returns_correct_timedelta(self):
        """max_age_for('price') should return correct TTL."""
        policy = CachePolicy(eod_prices_max_age_hours=12)
        ttl = policy.max_age_for("price")
        assert ttl == timedelta(hours=12)

    def test_max_age_for_fundamentals_returns_correct_timedelta(self):
        """max_age_for('fundamentals') should return correct TTL."""
        policy = CachePolicy(fundamentals_max_age_hours=48)
        ttl = policy.max_age_for("fundamentals")
        assert ttl == timedelta(hours=48)

    def test_max_age_for_unknown_returns_default(self):
        """max_age_for(unknown) should return default TTL."""
        policy = CachePolicy(default_max_age_hours=6)
        ttl = policy.max_age_for("unknown_type")
        assert ttl == timedelta(hours=6)
