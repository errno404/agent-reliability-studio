# Worker

The worker is the same Python package as the API (`ars-api`), started as a separate process:

```bash
ars worker                # poll the run_executions table, claim queued runs, execute, persist progress
ars worker --once         # claim and run one job, then exit (used in tests/CI)
```

Jobs are rows in `run_executions` (`queued → running → succeeded|failed`). A claim is one atomic
`UPDATE ... WHERE status='queued'`, so two workers can never take the same job. Workers heartbeat
while running; a job whose heartbeat is older than `STALE_JOB_SECONDS` is re-queued (max 3 attempts).
Execution resumes where it stopped because `samples` has a unique `(run_id, case_id, sample_index)`
key and finished samples are skipped. No Redis/Celery is needed.
