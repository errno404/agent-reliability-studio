# 0002 — PostgreSQL canonical, SQLite for zero-setup
**Status:** accepted
**Decision:** SQLAlchemy 2 + Alembic with `JSON` (JSONB on Postgres). Postgres is the deployment database; SQLite lets `make demo` work with no services. The job queue and tests run on both.
**Consequences:** One schema, two dialects (we avoid dialect-specific SQL). SQLite concurrency is fine for the demo; use Postgres for multi-worker.
