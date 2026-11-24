"""Lightweight Postgres/SQLite job queue on the run_executions table (no Redis/Celery)."""

from __future__ import annotations

import logging
import os
import socket
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Run, RunExecution
from . import runs as run_svc

log = logging.getLogger("ars.jobs")
MAX_ATTEMPTS = 3
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


def _now() -> datetime:
    return datetime.now(UTC)


def claim_next(s: Session, worker_id: str = WORKER_ID) -> RunExecution | None:
    """Atomically claim one queued job. UPDATE ... WHERE status='queued' makes the claim race-safe on both DBs."""
    cand = s.scalar(select(RunExecution.id).where(RunExecution.status == "queued").order_by(RunExecution.id).limit(1))
    if cand is None:
        return None
    res = s.execute(
        update(RunExecution)
        .where(RunExecution.id == cand, RunExecution.status == "queued")
        .values(
            status="running",
            worker_id=worker_id,
            started_at=_now(),
            heartbeat_at=_now(),
            attempt=RunExecution.attempt + 1,
        )
    )
    s.commit()
    if getattr(res, "rowcount", 0) != 1:  # lost the race to another worker
        return None
    return s.get(RunExecution, cand)


def recover_stale(s: Session, stale_seconds: int) -> int:
    """Re-queue running jobs whose heartbeat stopped. Idempotent; gives up after MAX_ATTEMPTS."""
    cutoff = _now() - timedelta(seconds=stale_seconds)
    n = 0
    for ex in s.scalars(select(RunExecution).where(RunExecution.status == "running")):
        hb = ex.heartbeat_at
        if hb is not None and hb.tzinfo is None:
            hb = hb.replace(tzinfo=UTC)
        if hb is None or hb < cutoff:
            if ex.attempt >= MAX_ATTEMPTS:
                ex.status, ex.error, ex.finished_at = "failed", "exceeded max attempts after stale heartbeat", _now()
                run = s.get(Run, ex.run_id)
                if run:
                    run.status, run.error = "failed", ex.error
            else:
                ex.status = "queued"
            n += 1
    s.commit()
    return n


def run_job(s: Session, ex: RunExecution) -> None:
    run = s.get(Run, ex.run_id)
    assert run is not None

    def beat() -> None:
        ex.heartbeat_at = _now()
        s.commit()

    try:
        run_svc.execute_run(s, run, heartbeat=beat)
        ex.status, ex.finished_at = "succeeded", _now()
    except Exception as exc:  # job failure is recorded, never silently swallowed
        s.rollback()
        log.exception("job %s failed", ex.id, extra={"run_id": run.id, "job_id": ex.id})
        ex = s.get(RunExecution, ex.id)  # type: ignore[assignment]
        run = s.get(Run, run.id)  # type: ignore[assignment]
        ex.status, ex.error, ex.finished_at = "failed", f"{type(exc).__name__}: {exc}"[:500], _now()  # type: ignore[union-attr]
        run.status, run.error = "failed", ex.error  # type: ignore[union-attr]
    s.commit()


def work_once(s: Session, stale_seconds: int = 120) -> bool:
    recover_stale(s, stale_seconds)
    ex = claim_next(s)
    if ex is None:
        return False
    log.info("claimed job", extra={"job_id": ex.id, "run_id": ex.run_id})
    run_job(s, ex)
    return True
