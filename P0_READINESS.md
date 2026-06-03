# P0 / CP0 Readiness Report

Date: 2026-06-03

## Current verdict

**CP0 is partially passed.** G0.1 is now satisfied because the upstream TradingAgents baseline is present in this repository. G0.2 is satisfied for repository-side runtime/secret boundaries. G0.3 is blocked by missing local provider credentials, not by missing code.

## Evidence checked

- TradingAgents baseline is vendored at `vendor/TradingAgents/` from upstream commit `04f434e86db88e7707bf16db8ed7183f9764fe26`.
- License/attribution is preserved at `vendor/TradingAgents/LICENSE` and documented in `docs/TRADINGAGENTS_BASELINE.md`.
- Required fork surfaces are present:
  - CLI: `vendor/TradingAgents/cli/main.py`
  - dataflows/data toolkit: `vendor/TradingAgents/tradingagents/dataflows/`
  - council graph/debate orchestration: `vendor/TradingAgents/tradingagents/graph/`
  - agent package/persona surfaces: `vendor/TradingAgents/tradingagents/agents/`
  - upstream tests: `vendor/TradingAgents/tests/`
- Runtime package metadata is present at `vendor/TradingAgents/pyproject.toml`.
- Local compile verification passed with `python3 -m compileall -q vendor/TradingAgents/tradingagents vendor/TradingAgents/cli`.
- Editable install dry-run passed with `python3 -m venv /tmp/fincouncil-ta-venv` and `pip install -e vendor/TradingAgents --dry-run`.

## Safe artifacts added for G0.2

- `.env.example` lists required key names only, with empty values.
- `.gitignore` excludes secrets, local virtualenv/cache files, DuckDB files, parquet warehouse/cache outputs.
- `fincouncil/` namespace scaffold matches `PROJECT_SETUP.md` so later fork-extension work has a local home that does not rewrite upstream TradingAgents internals.
- `docs/CP0_BASELINE_SMOKE.md` records the baseline verification and credential blocker.

## G0 status

- **G0.1 — Fork baseline present:** PASS.
- **G0.2 — Reproducible runtime + secret boundary:** PASS for repository-side setup; dependency install path is documented in `docs/CP0_BASELINE_SMOKE.md`.
- **G0.3 — Baseline council smoke:** BLOCKED by missing local provider credentials. During this session, no real values were present for `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `ZHIPU_API_KEY`, `DASHSCOPE_API_KEY`, `DASHSCOPE_CN_API_KEY`, or `ALPHA_VANTAGE_API_KEY`.

## Hard gate before Phase 1 tasks

Do not start Phase 1 data-layer implementation (`T1.1` onward) until G0.3 is completed with real local credentials, or until the project explicitly accepts the documented credential blocker as sufficient CP0 evidence for offline planning only.

## Next executable step

Install the vendored baseline in an isolated environment, provide local GLM/zai or other supported provider credentials through `.env`/environment variables, then run a baseline CLI smoke on one US ticker and append the real log to `docs/CP0_BASELINE_SMOKE.md`.
