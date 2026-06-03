# TradingAgents Baseline Attribution

Date: 2026-06-03

FinCouncil vendors the `TauricResearch/TradingAgents` baseline under `vendor/TradingAgents/` so the project can extend the proven council/orchestration implementation instead of rebuilding it.

## Upstream

- Repository: https://github.com/TauricResearch/TradingAgents
- Imported commit: 04f434e86db88e7707bf16db8ed7183f9764fe26
- License: Apache-2.0; see `vendor/TradingAgents/LICENSE`

## Local integration rule

- Keep upstream baseline code recognizable and attributable.
- Add FinCouncil-specific data-layer, reconcile, MCP, routing, valuation, and eval-gate work around/through the fork instead of rewriting council/debate/CLI/persona orchestration.
- Secrets remain outside git; use `.env` locally and `.env.example` for key names only.
