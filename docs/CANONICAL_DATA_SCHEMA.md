# Canonical Data Schema — Phase 1 / T1.1

This contract is the source of truth for Phase 1 data-layer records consumed by
normalization, DuckDB storage, reconcile, MCP tools, and the later
TradingAgents data shim. It is intentionally provider-neutral: raw adapter
payloads stay outside this schema until normalized.

## Universal audit fields

Every canonical record type **must** include these fields:

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| `source` | string | yes | Provider or normalized pipeline name, non-empty. |
| `currency` | ISO-4217 string | yes | Three uppercase letters such as `USD`, `JPY`, `THB`, `HKD`, `CNY`. |
| `as_of` | date/datetime | yes | When the record or provider value is considered current/auditable. |

## `price`

End-of-day OHLCV record. Monetary fields are quoted in `currency`.

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| `kind` | literal `price` | yes | Record discriminator. |
| `symbol` | string | yes | Canonical `{exchange}:{ticker}` symbol. |
| `date` | date | yes | Trading date. |
| `open` | Decimal | yes | Non-negative. |
| `high` | Decimal | yes | Non-negative; must be >= `low`. |
| `low` | Decimal | yes | Non-negative; must be <= `high`. |
| `close` | Decimal | yes | Non-negative; within `low`/`high`. |
| `volume` | integer | yes | Non-negative provider-reported share/unit count. |
| `adjusted_close` | Decimal | yes | Split/dividend-adjusted close when provider supports it; otherwise equals `close` and the normalizer must document that provider behavior. |
| `source`, `currency`, `as_of` | see universal fields | yes | Required on every record. |

## `fundamentals`

Financial statement and ratio record. Statement values are quoted in `currency`;
ratios/per-share fields use their natural units. Optional fields allow provider
and market differences, but at least one core statement value is required.

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| `kind` | literal `fundamentals` | yes | Record discriminator. |
| `symbol` | string | yes | Canonical `{exchange}:{ticker}` symbol. |
| `period` | enum `FY`/`Q` | yes | Fiscal year or quarter. |
| `fiscal_date` | date | yes | Fiscal period end date. |
| `revenue` | Decimal | conditional | Core statement value. |
| `gross_profit` | Decimal | optional | Core statement value. |
| `operating_income` | Decimal | optional | Core statement value. |
| `net_income` | Decimal | optional | Core statement value. |
| `total_assets` | Decimal | optional | Core statement value. |
| `total_liabilities` | Decimal | optional | Core statement value. |
| `shareholders_equity` | Decimal | optional | Core statement value. |
| `operating_cash_flow` | Decimal | optional | Core statement value. |
| `capital_expenditure` | Decimal | optional | Core statement value. |
| `free_cash_flow` | Decimal | optional | Core statement value. |
| `eps` | Decimal | optional | Earnings per share. |
| `pe_ratio` | Decimal | optional | Price/earnings ratio. |
| `pb_ratio` | Decimal | optional | Price/book ratio. |
| `roe` | Decimal | optional | Return on equity. |
| `debt_to_equity` | Decimal | optional | Leverage ratio. |
| `source`, `currency`, `as_of` | see universal fields | yes | Required on every record. |

## `symbol`

Canonical instrument identity and provider mapping record.

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| `kind` | literal `symbol` | yes | Record discriminator. |
| `symbol` | string | yes | Canonical `{exchange}:{ticker}` symbol. |
| `exchange` | string | yes | Exchange/venue code used in the canonical prefix. |
| `ticker` | string | yes | Local ticker without provider suffix. |
| `provider_symbols` | mapping string→string | yes | At least one provider-specific symbol/suffix mapping. |
| `name` | string | optional | Issuer/security display name. |
| `country` | string | optional | ISO country or market label when known. |
| `asset_type` | string | yes | Defaults to `equity`; later phases may add other asset types. |
| `source`, `currency`, `as_of` | see universal fields | yes | Required on every record, even for symbols. |

## `reconcile_log`

Audit record for comparing the same field from two or more sources.

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| `kind` | literal `reconcile_log` | yes | Record discriminator. |
| `symbol` | string | yes | Canonical `{exchange}:{ticker}` symbol. |
| `field` | string | yes | Compared field name, for example `close` or `revenue`. |
| `date` | date | yes | Trading date or fiscal period date for the compared value. |
| `values` | mapping source→Decimal | yes | Values from at least two sources. |
| `diff_pct` | Decimal | yes | Non-negative percentage difference. |
| `threshold_pct` | Decimal | yes | Non-negative threshold used for this comparison. |
| `status` | enum `PASS`/`FLAG` | yes | `FLAG` means discrepancy exceeded threshold. |
| `explanation` | string | yes | Human-readable reason; discrepancies must surface, not be swallowed. |
| `source`, `currency`, `as_of` | see universal fields | yes | Required on every record; `source` should identify the reconcile engine/config. |

## Runtime contract

The dependency-free Python implementation lives in `fincouncil/data/schema.py`.
Use `validate_record(record)` before writing normalized records to storage,
returning them through MCP, or passing them into reconcile.
