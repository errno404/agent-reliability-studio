# Third-party notices

## Research inputs (concepts only — no code copied)

Before designing this project I cloned and read two public repositories. Both are MIT-licensed. **No source files, tests,
datasets, prompts or fixtures were copied or adapted from either.** Everything here (code, datasets, fixtures, UI, docs) was
written for this project. Credit is given for the *ideas* that shaped the design:

| Project | License | Ideas we studied and re-implemented originally |
|---|---|---|
| [cryer/agent-eval](https://github.com/cryer/agent-eval) | MIT | paired case-level bootstrap and McNemar for regression decisions; calibration-gated judges (50 items / 10 per class / κ ≥ 0.6 / FPR ≤ 5%); run manifests and pair validation; trajectory diffing; trace-to-case distillation; same-evaluator baseline/candidate CI |
| [anapsousa/agent-reliability-lab](https://github.com/anapsousa/agent-reliability-lab) | MIT | frozen, pinned agent versions (`PINS.md`); separate outcome / trajectory / component scoring; repeated-run `pass^k`; MCP fixture web; human-label calibration; written lessons on evaluator mistakes (e.g. that tolerances must reflect sample size) |

Where this project goes further: clustered paired bootstrap that keeps repeated samples of a case together; Wilson
intervals on every rate; five-state comparison verdicts with explicit INVALID / INCONCLUSIVE; execution errors separated from
quality failures everywhere; judge identity = (backend, model, prompt hash) enforced at the gate; strict-vs-exploratory
comparison modes; OpenTelemetry GenAI traces with redaction before storage/export; a full dashboard.

If a future contribution does reuse code from either project, add the file path, the original copyright notice and the MIT
text here before merging.

## Runtime dependencies

Used under their own licenses (all permissive): FastAPI, Starlette, Pydantic, SQLAlchemy, Alembic, Typer, Rich, uvicorn,
psycopg (LGPL-3.0, dynamically linked, unmodified), PyYAML, jsonschema, OpenTelemetry SDK/API (Apache-2.0), the official MCP
Python SDK (MIT), LangGraph (MIT), LiteLLM (MIT, optional), Inspect AI (MIT, optional); Next.js, React, Tailwind CSS,
Recharts, TanStack Table, lucide-react (ISC), Geist fonts (SIL OFL 1.1), Playwright (Apache-2.0), Vitest (MIT).
Exact versions are pinned in `uv.lock` and `apps/web/package-lock.json`.
