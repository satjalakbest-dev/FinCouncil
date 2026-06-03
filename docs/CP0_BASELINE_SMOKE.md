# CP0 Baseline Smoke Log

Date: 2026-06-03

## Scope

Verify that FinCouncil now contains the upstream TradingAgents baseline required before Phase 1 data-layer implementation.

## Baseline imported

- Location: `vendor/TradingAgents/`
- Upstream: `TauricResearch/TradingAgents`
- Imported commit: `04f434e86db88e7707bf16db8ed7183f9764fe26`
- License/attribution: `vendor/TradingAgents/LICENSE`, plus `docs/TRADINGAGENTS_BASELINE.md`

## Structural evidence

Present in the imported baseline:

- CLI: `vendor/TradingAgents/cli/main.py`
- Data toolkit/dataflows: `vendor/TradingAgents/tradingagents/dataflows/`
- Council graph/debate orchestration: `vendor/TradingAgents/tradingagents/graph/`
- Agent package/persona surfaces: `vendor/TradingAgents/tradingagents/agents/`
- Upstream tests: `vendor/TradingAgents/tests/`
- Runtime package metadata: `vendor/TradingAgents/pyproject.toml`

## Runtime/install path

From a fresh checkout, install the baseline in an isolated environment from the vendored fork root, for example:

```bash
cd vendor/TradingAgents
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Secrets must be supplied locally through `.env` or environment variables only; do not commit them.

## Verification run in this session

```bash
python3 -m compileall -q vendor/TradingAgents/tradingagents vendor/TradingAgents/cli
```

Result: passed. One upstream syntax warning was emitted in `vendor/TradingAgents/cli/utils.py` for an invalid escape sequence in a docstring; it does not block bytecode compilation.

## Install-path dry run

```bash
python3 -m venv /tmp/fincouncil-ta-venv
/tmp/fincouncil-ta-venv/bin/python -m pip install -e vendor/TradingAgents --dry-run
```

Result: passed. Pip resolved the editable `tradingagents==0.2.5` package and dependencies without installing them into the repository.

## Credential check

The following provider credentials were not present in the process environment during this session:

- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- `ZHIPU_API_KEY`
- `DASHSCOPE_API_KEY`
- `DASHSCOPE_CN_API_KEY`
- `ALPHA_VANTAGE_API_KEY`

## G0.3 status

Baseline CLI thesis smoke on a live US ticker is **blocked by missing local provider credentials only**. No fabricated financial output was generated and no Phase 1 data-layer implementation was started.
