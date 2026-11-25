# Architecture

![Architecture](images/architecture.svg)

Source for the diagram: [`architecture.mmd`](architecture.mmd).

## Components and boundaries

| Component | Responsibility | Must not |
|---|---|---|
| `packages/evalcore` | Domain models, 22 assertions, scoring layers, statistics, calibration, judge, manifest + comparison validation, tracing/redaction, taxonomy, trajectory diff, distillation, adapters | import FastAPI/SQLAlchemy/web code |
| `packages/demo_agents` | Frozen reference systems under test (support, research, coding) and the `Runtime` harness (virtual clock, OTel spans, seeded fault injection) | contain evaluation logic |
| `mcp/fixture_web` | Deterministic, read-only synthetic web (29 pages) served by the **official MCP SDK** | touch the internet |
| `services/api` | REST API, SQLAlchemy models, Alembic migrations, job queue + worker, `ars` CLI, idempotent seed | duplicate logic between API/CLI/worker (they share `app/services/*`) |
| `apps/web` | Next.js dashboard; typed client generated from OpenAPI; **runtime `/api` proxy** | call the API with a build-time URL |
| `integrations/*` | Inspect AI export/ingest; Phoenix/OTLP mirror | become a dependency of the core |

## Data flow of one evaluation run

```
dataset YAML ──load_and_validate──▶ hash ──sync_dataset──▶ dataset_versions + eval_cases (FROZEN if published)
agent spec "support:v2" ──agent_info──▶ agent_versions (code hash, prompt hash, tool-schema hash)
create_run ─▶ runs + manifest (dataset/fixture/judge/model/seed/git/evaluator…) + manifest_hash ─▶ run_executions (queued)
worker claims job (atomic UPDATE) ─▶ for each (case, sample_index):
      adapter.run(case) ─▶ AgentResult (tool calls, tokens, latency, state, spans — redacted)
      evaluate_all(assertions) + trajectory checks (+ judge if admitted) ─▶ SampleResult(status, labels)
      persisted: samples · assertion_results · spans · failure_labels      (resume-safe: unique(run, case, sample_index))
finalize_run ─▶ summary (layer rates + Wilson CI, pass^k, pass@k, latency p50/p95, tokens, cost) + failure_clusters
create_comparison ─▶ validate_pair (strict|exploratory) ─▶ paired cluster bootstrap ─▶ decision ─▶ create_gate ─▶ ci_gate_decisions
```

## Database (20 tables)

`agents · agent_versions · datasets · dataset_versions · eval_cases · runs · run_executions · samples · spans · assertion_results ·
failure_labels · failure_clusters · judge_configs · calibration_sets · calibration_items · calibration_runs · human_annotations ·
comparisons · ci_gate_decisions · distilled_candidates`. JSON(B) is used only for genuinely free-form payloads (span attributes, case
definitions, manifests, comparison results). Indexes cover run lookups, agent/version joins, `(run, status)`, trace lookup, failure
label filtering, and timestamp sorting. Lists are paginated; serializers use joined loads (no N+1).

## Jobs

`run_executions` is the queue. `claim_next` performs one atomic `UPDATE … WHERE id=? AND status='queued'` (race-safe on SQLite and
Postgres). Workers heartbeat; `recover_stale` re-queues jobs whose heartbeat stopped (max 3 attempts, idempotent). Because samples have a
unique `(run_id, case_id, sample_index)` key and finished samples are skipped, a resumed job never duplicates work. No Redis/Celery.

## Tracing

`evalcore.tracing.TraceRecorder` creates real OpenTelemetry SDK spans with a **virtual clock** (reproducible timings) and copies redacted
attributes into `SpanRecord`s. Attribute names come from `evalcore/semconv.py` (the single GenAI-convention mapping; `gen_ai.operation.name`
∈ `invoke_agent | chat | execute_tool | retrieval`, `gen_ai.provider.name`, `gen_ai.usage.*`, `gen_ai.tool.*`). Exporters (e.g. OTLP→Phoenix)
only ever see redacted data. The DB span table is the source of truth for the dashboard.

## API and frontend

FastAPI exposes typed read endpoints (overview, runs, samples, traces, comparisons, case diffs, failures, judges, calibration, annotation,
gates, datasets) plus admin-only mutations. `ars openapi` exports the spec; `openapi-typescript` generates `lib/api-types.ts`. Server components
fetch directly from `API_URL`; the browser calls same-origin `/api/*`, which a route handler forwards to `API_URL` **at runtime** (one build runs anywhere).

## Deployment topologies

- **Local:** SQLite file, `make dev`.
- **Compose:** Postgres + API (loopback-published) + web; Phoenix behind `--profile observability`.
- **Render:** free-tier-compatible blueprint (`render.yaml`): free Postgres (expires after 30 days), free API *web* service in read-only demo mode, free web tier. Private services have no free tier. Not deployed by this repo's tooling. The API seeds the synthetic demo on first start (idempotent).
