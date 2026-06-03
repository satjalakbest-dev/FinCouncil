from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("duckdb")

from fincouncil.data.store import DuckDBWarehouse


def sample_prices() -> list[dict[str, object]]:
    return [
        {
            "symbol": "US:AAPL",
            "date": "2026-01-02",
            "open": 100.0,
            "high": 110.0,
            "low": 99.0,
            "close": 108.0,
            "volume": 1000,
            "currency": "USD",
            "source": "test",
        },
        {
            "symbol": "US:AAPL",
            "date": "2026-01-03",
            "open": 108.0,
            "high": 112.0,
            "low": 107.0,
            "close": 111.0,
            "volume": 1500,
            "currency": "USD",
            "source": "test",
        },
        {
            "symbol": "JP:7011",
            "date": "2026-01-03",
            "open": 900.0,
            "high": 910.0,
            "low": 890.0,
            "close": 905.0,
            "volume": 2000,
            "currency": "JPY",
            "source": "test",
        },
    ]


def test_prices_round_trip_and_date_range(tmp_path: Path) -> None:
    warehouse = DuckDBWarehouse(tmp_path / "warehouse.duckdb")
    try:
        assert warehouse.upsert_prices(sample_prices()) == 3

        result = warehouse.query_prices("US:AAPL", "2026-01-03", "2026-01-03")

        assert result["symbol"].tolist() == ["US:AAPL"]
        assert result["date"].tolist() == [pd.Timestamp("2026-01-03")]
        assert result["close"].tolist() == [111.0]
        assert result["volume"].tolist() == [1500]
    finally:
        warehouse.close()


def test_price_upsert_is_idempotent_and_updates_existing_row(tmp_path: Path) -> None:
    warehouse = DuckDBWarehouse(tmp_path / "warehouse.duckdb")
    try:
        rows = sample_prices()
        warehouse.upsert_prices(rows)
        warehouse.upsert_prices(rows)

        assert warehouse.price_count() == 3

        correction = dict(rows[0], close=109.5, volume=1200)
        warehouse.upsert_prices([correction])

        assert warehouse.price_count() == 3
        result = warehouse.query_prices("US:AAPL", "2026-01-02", "2026-01-02")
        assert result["close"].tolist() == [109.5]
        assert result["volume"].tolist() == [1200]
    finally:
        warehouse.close()


def test_export_prices_parquet_partitions_by_symbol_and_date(tmp_path: Path) -> None:
    warehouse = DuckDBWarehouse(
        tmp_path / "warehouse.duckdb",
        parquet_root=tmp_path / "parquet" / "prices",
    )
    try:
        warehouse.upsert_prices(sample_prices())
        export_root = warehouse.export_prices_parquet()

        parquet_files = sorted(export_root.glob("symbol=*/date=*/*.parquet"))
        assert len(parquet_files) == 3
        assert (export_root / "symbol=US%3AAAPL").exists()
        assert any("date=2026-01-03" in str(path) for path in parquet_files)
    finally:
        warehouse.close()
