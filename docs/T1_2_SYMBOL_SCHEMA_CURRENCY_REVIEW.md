# T1.2 Symbol + Schema/Currency Review

Task 4 review scope: independently cross-check the T1.2 symbol convention against
the T1.1 schema contract and currency requirements before downstream mapping code
is integrated.

## Source references

- `PHASE1_DATA_LAYER_SPRINT.md:50-54` requires canonical `{exchange}:{ticker}`
  mapping to provider suffixes for US, `.T`, `.BK`, `.HK`, `.SS`, and `.SZ`, with
  round-trip fixture agreement on AAPL, 7011, PTT, 00700, and 600519.
- `PHASE1_DATA_LAYER_SPRINT.md:44-48` and `DATA_SOURCES.md:1-2` require every
  record to include `source`, `currency`, and `as_of`.
- `DATA_SOURCES.md:10-15` establishes the first Phase 1 market/currency surface:
  US, global, China A-share, Hong Kong, Japan, and Thai SET price coverage.

## Cross-check fixture expectations

| Canonical symbol | Exchange | Ticker | Provider fixture | Currency |
|---|---|---|---|---|
| `NASDAQ:AAPL` | `NASDAQ` | `AAPL` | `AAPL` | `USD` |
| `TSE:7011` | `TSE` | `7011` | `7011.T` | `JPY` |
| `SET:PTT` | `SET` | `PTT` | `PTT.BK` | `THB` |
| `HKEX:00700` | `HKEX` | `00700` | `00700.HK` | `HKD` |
| `SSE:600519` | `SSE` | `600519` | `600519.SS` | `CNY` |
| `SZSE:000001` | `SZSE` | `000001` | `000001.SZ` | `CNY` |

## Review findings

- PASS: T1.1 schema documents and validates `source`, uppercase ISO-style
  `currency`, and `as_of` across `price`, `fundamentals`, `symbol`, and
  `reconcile_log` records.
- PASS: `SymbolRecord` now rejects canonical symbols whose `{exchange}:{ticker}`
  text does not match the separate `exchange` and `ticker` fields, preventing
  provider mapping from silently routing a mismatched instrument.
- PASS: Tests cover all T1.2 provider suffix classes named in the sprint: no
  suffix for US, `.T`, `.BK`, `.HK`, `.SS`, and `.SZ`.
- WATCH: Provider-specific mapping/round-trip functions are not implemented in
  this review lane; downstream T1.2 implementation should use the fixture table
  above and preserve leading-zero tickers such as `00700` and `000001`.
- WATCH: Currency is validated structurally as uppercase three-letter code, not
  against a full ISO-4217 registry. This is sufficient for Phase 1 contracts and
  avoids a new dependency; provider normalizers should still source currency from
  provider metadata rather than inference when possible.
