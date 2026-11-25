# 15. Job leases and fencing (single-database)

Status: accepted (2026-11-25)

## Context
The queue used a heartbeat written from the working thread (every N samples), so a slow sample looked like a dead worker; recovery read-then-wrote; a stale worker could still commit.

## Decision
Lease token + expiry on `run_executions`; an independent heartbeat thread with its own session (ownership validated by `UPDATE … WHERE lease_token=?`); rowcount-checked recovery;
bounded attempts; fence before every write batch and token-conditional terminal transitions; unique `(run, case, sample)` as the last line of defence.

## Consequences
+ verified with concurrent claims/recoveries, slow jobs and takeover on SQLite and PostgreSQL. - a small check-then-write window remains and this is **not** distributed consensus; do not claim more.
