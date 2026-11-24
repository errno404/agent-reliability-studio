---
name: backend-engineering
description: Backend conventions for the FastAPI/SQLAlchemy/worker stack. Use when changing services/api, migrations, the job queue, the CLI or seeding.
---
# Backend conventions
- `evalcore` stays framework-free; API, CLI and worker call `services/api/app/services/*` (single service layer).
- Schema changes need an Alembic migration (`uv run alembic -c services/api/alembic.ini revision --autogenerate`; fix JSONB `astext_type=sa.Text()` if emitted). Postgres is canonical, SQLite supported; use the `Json` variant type.
- Jobs are rows in `run_executions`; claim = one atomic `UPDATE … WHERE status='queued'`; heartbeat + stale recovery; resume is idempotent via the `(run_id, case_id, sample_index)` unique key. No Redis/Celery.
- Seeds and scripts must be idempotent (run twice ⇒ identical counts). Frozen datasets are never mutated.
- Mutating endpoints depend on `require_admin` (403 in demo mode). Annotation/adjudication are the only public writes: rate-limited, capped, append-only, validated with `fullmatch`.
- Pagination on lists; joinedload to avoid N+1. Structured JSON logs with request/run/job/case ids; never log prompt content. Production hides exception details.
- Quality gates: `ruff`, `pyright` (0 errors), `pytest`. Run `source scripts/env.sh` first.
