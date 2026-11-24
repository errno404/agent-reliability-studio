# BUILD_STATE — internal engineering continuity (not marketing docs)

Source spec: `SPEC.md` (source of truth). After compaction/interruption read: `CLAUDE.md`, this file, `docs/adr/`, `git status`.

## Environment (verified 2026-11-24)
- Python 3.13 (uv-managed, `uv sync --python 3.13`); uv 0.13; node 20.19 (npm; **do not use pnpm** — a stray `~/package.json` with `packageManager: yarn` breaks corepack); docker 29; `claude` CLI NOT installed locally (Claude Code adapter tested with a fake binary); `gh` present.
- Pinned (verified against PyPI/npm 2026-11-24): fastapi 0.165, pydantic 2.14, sqlalchemy 2.1, alembic 1.20, mcp 2.3 (**FastMCP renamed `MCPServer`**, `from mcp.server.mcpserver import MCPServer`), opentelemetry 1.45 / semconv 0.66b2, langgraph 1.2, next 16.4, react 19.3, tailwind 4.3, recharts 3.11, playwright 1.65.
- OTel GenAI attrs used: `gen_ai.operation.name` (`invoke_agent`/`chat`/`execute_tool`/`retrieval`), `gen_ai.provider.name` (replaces deprecated `gen_ai.system`), `gen_ai.request.model`, `gen_ai.usage.input_tokens|output_tokens`, `gen_ai.tool.name`, `gen_ai.tool.call.arguments|result`, `gen_ai.agent.name|version`. All mapped in one module: `evalcore/semconv.py`.

## Research notes (reference repos cloned to scratchpad, NOT committed)
- cryer/agent-eval (MIT, ~3100 LOC): paired case-bootstrap, McNemar, classify_delta w/ margin, calibration admission (50/10/κ.6/FPR.05), run-execution manifests, validate_run_pair. Limitations we fix: no clustered handling of unequal samples/case beyond mean-per-case; no Wilson CI; boolean-only labels; judge identity not enforced at gate by hash across versions in a typed model; no separate execution_error vs fail in comparisons beyond a check.
- anapsousa/agent-reliability-lab (MIT): pinning rule (PINS.md), pass^k, tolerance revised 5→15pts because one 40-task run resolves ~±15, CLAUDE.md conventions. We implement concepts originally; no code copied (see THIRD_PARTY_NOTICES.md).

## Architecture decisions (also ADRs in docs/adr)
- uv workspace: `evalcore` (pure, no FastAPI), `demo_agents`, `fixture_web` (MCP), `ars-api` (FastAPI + SQLAlchemy + worker + `ars` CLI).
- DB: SQLAlchemy 2 + Alembic; Postgres canonical, SQLite default for zero-setup. Job table + worker polling (no Redis).
- Demo mode: `DEMO_MODE=true` → read-only API (mutations 403), seeded synthetic data.
- Frontend: Next.js (App Router) in `apps/web`, talks to API via typed client in `lib/api.ts`.

## Checklist (mark [x] when RUN + TESTED + INSPECTED)
- [ ] evalcore: models, dataset load/hash, assertions (22), scoring layers, stats, calibration, judge, compare/validation, manifest, tracing+redaction, taxonomy, distill, runner, adapters, pricing, simulation
- [ ] demo_agents: support v1/v2, research v1/v2 (LangGraph), coding v1/v2, PINS.md, seeded variance
- [ ] fixture web MCP server + corpus
- [ ] datasets: support 30, research 20, coding 10, redteam 15-20, calibration 50+
- [ ] API + DB + migrations + worker + CLI + seed + verify
- [ ] Dashboard (9 nav pages, annotation UI, case compare, trace waterfall)
- [ ] Inspect AI integration; Phoenix profile
- [ ] CI workflows, pin-check script, Docker, render.yaml
- [ ] Docs (README, ARCHITECTURE, EVAL_METHODOLOGY, LEARNING_GUIDE, DEMO, SECURITY, ADRs), screenshots, diagram
- [ ] .claude skills + agents, CLAUDE.md
- [ ] Final review passes, full verification, completion report

## Current commands
`uv sync --python 3.13` · `uv run pytest` · `uv run ruff check .` · `uv run pyright`

## Migration state / test status / known issues
(none yet)

## Next action
Write evalcore models + stats.
