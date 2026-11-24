# 0011 — Job queue on the database, no Redis/Celery
**Status:** accepted
**Decision:** `run_executions` rows are jobs; claim by atomic `UPDATE … WHERE status='queued'`; heartbeat + idempotent stale recovery (max 3 attempts); resume via the unique `(run, case, sample_index)` key.
**Consequences:** Fewer moving parts; polling latency; fine for evaluation-scale workloads.
