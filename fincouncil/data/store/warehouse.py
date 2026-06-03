"""DuckDB warehouse primitives for normalized FinCouncil market data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

try:  # Keep import-time errors actionable for environments missing optional deps.
    import duckdb
except ImportError as exc:  # pragma: no cover - exercised only when dependency missing.
    raise ImportError(
        "DuckDBWarehouse requires the 'duckdb' package. Install project data-layer "
        "dependencies before using fincouncil.data.store."
    ) from exc


_PRICE_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "currency",
    "source",
]


class DuckDBWarehouse:
    """Small DuckDB warehouse facade with idempotent normalized-data writes."""

    def __init__(self, db_path: str | Path = ":memory:", parquet_root: str | Path | None = None) -> None:
        self.db_path = str(db_path)
        self.parquet_root = Path(parquet_root) if parquet_root is not None else None
        self._connection = duckdb.connect(self.db_path)
        self.initialize()

    def close(self) -> None:
        self._connection.close()

    def initialize(self) -> None:
        """Create the Phase 1 warehouse tables if they do not already exist."""
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                currency VARCHAR,
                source VARCHAR NOT NULL DEFAULT 'unknown',
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                PRIMARY KEY (symbol, date, source)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fundamentals (
                symbol VARCHAR NOT NULL,
                period_end DATE NOT NULL,
                metric VARCHAR NOT NULL,
                value DOUBLE,
                currency VARCHAR,
                source VARCHAR NOT NULL DEFAULT 'unknown',
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                PRIMARY KEY (symbol, period_end, metric, source)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS symbols (
                symbol VARCHAR PRIMARY KEY,
                exchange VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                name VARCHAR,
                currency VARCHAR,
                source VARCHAR,
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reconcile_log (
                run_id VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                message VARCHAR,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """
        )

    def upsert_prices(self, rows: Iterable[Mapping[str, Any]] | pd.DataFrame) -> int:
        """Insert or update normalized price rows by ``(symbol, date, source)``.

        Returns the number of input rows accepted. Repeating the same rows is
        idempotent because the DuckDB primary key conflict path updates the
        existing row instead of appending a duplicate.
        """
        frame = self._coerce_prices(rows)
        if frame.empty:
            return 0

        self._connection.register("price_rows", frame)
        try:
            self._connection.execute(
                """
                INSERT INTO prices BY NAME
                SELECT
                    symbol,
                    CAST(date AS DATE) AS date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    currency,
                    source,
                    current_timestamp AS updated_at
                FROM price_rows
                ON CONFLICT (symbol, date, source) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    currency = excluded.currency,
                    updated_at = excluded.updated_at
                """
            )
        finally:
            self._connection.unregister("price_rows")
        return len(frame)

    def query_prices(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        *,
        source: str | None = None,
    ) -> pd.DataFrame:
        """Read prices for a symbol in an inclusive date range."""
        params: list[Any] = [symbol, start_date, end_date]
        source_clause = ""
        if source is not None:
            source_clause = " AND source = ?"
            params.append(source)

        return self._connection.execute(
            f"""
            SELECT symbol, date, open, high, low, close, volume, currency, source
            FROM prices
            WHERE symbol = ?
              AND date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
              {source_clause}
            ORDER BY date ASC, source ASC
            """,
            params,
        ).fetchdf()

    def export_prices_parquet(self, root: str | Path | None = None) -> Path:
        """Export prices to Parquet partitioned by symbol and date."""
        export_root = Path(root) if root is not None else self.parquet_root
        if export_root is None:
            raise ValueError("parquet root is required for price export")
        export_root.mkdir(parents=True, exist_ok=True)
        self._connection.execute(
            """
            COPY (
                SELECT *
                FROM prices
                ORDER BY symbol, date, source
            ) TO ? (FORMAT PARQUET, PARTITION_BY (symbol, date), OVERWRITE_OR_IGNORE 1)
            """,
            [str(export_root)],
        )
        return export_root

    def price_count(self) -> int:
        row = self._connection.execute("SELECT count(*) FROM prices").fetchone()
        if row is None:
            return 0
        return int(row[0])

    @staticmethod
    def _coerce_prices(rows: Iterable[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
        frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
        missing = [column for column in _PRICE_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"price rows missing required columns: {', '.join(missing)}")
        frame = frame.loc[:, _PRICE_COLUMNS].copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        return frame
