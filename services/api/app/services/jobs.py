"""Lightweight Postgres/SQLite job queue on the run_executions table (no Redis/Celery), with LEASES and FENCING.

Design (what is and is not guaranteed)
--------------------------------------
* **Claim** is a compare-and-set ``UPDATE ... WHERE id=? AND status='queued'``; exactly one concurrent claimant sees rowcount 1.
  The claimant receives a random ``lease_token`` and a ``lease_expires_at``.
* **Heartbeat** runs in an INDEPENDENT thread with its own database session, so a long sample (a live model call can take minutes)
  cannot starve it. Each beat is ``UPDATE ... WHERE id=? AND lease_token=? AND status='running'``: ownership is validated by the
  database; rowcount 0 means the lease was lost and the worker is told to stop.
* **Stale recovery** is a rowcount-checked ``UPDATE`` per execution, so two recoverers cannot both re-queue (or both fail) the same
  job. Attempts are bounded (``MAX_ATTEMPTS``); after that the run is marked failed, never retried forever.
* **Fencing**: before every batch of writes the worker re-checks the lease (``Lease.valid``) and every terminal state change is
  conditional on the token. A worker that lost its lease raises :class:`LeaseLost`, writes nothing more, and cannot mark the job or
  run finished. Sample inserts are also idempotent at the database level (unique ``(run_id, case_id, sample_index)``), so a
  duplicate insert from a racing stale worker fails loudly instead of corrupting results.
* **Verified**: SQLite (threads) and, when ``ARS_TEST_POSTGRES_URL`` is set, PostgreSQL. A single database transaction is not
  taken around "check lease + insert", so there is a small window between the check and the insert; the unique constraint and the
  token-conditional completion close the *damage*, but this is a single-database lease, not a distributed-consensus guarantee.
"""

from __future__ import annotations

import logging
import os
import re as _re
import secrets
import socket
import threading
from datetime import UTC, datetime, timedelta

from evalcore.redaction import Redactor as _Redactor
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Run, RunExecution
from . import runs as run_svc

log = logging.getLogger("ars.jobs")
MAX_ATTEMPTS = 3
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


def _now() -> datetime:
    return datetime.now(UTC)


def claim_next(s: Session, worker_id: str = WORKER_ID, lease_seconds: int = 120) -> RunExecution | None:
    """Atomically claim one queued job and take a lease on it."""
    cand = s.scalar(select(RunExecution.id).where(RunExecution.status == "queued").order_by(RunExecution.id).limit(1))
    if cand is None:
        return None
    now = _now()
    res = s.execute(
        update(RunExecution)
        .where(RunExecution.id == cand, RunExecution.status == "queued")
        .values(
            status="running",
            worker_id=worker_id,
            started_at=now,
            heartbeat_at=now,
            lease_token=secrets.token_hex(16),
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            attempt=RunExecution.attempt + 1,
        )
    )
    s.commit()
    if getattr(res, "rowcount", 0) != 1:  # lost the race to another worker
        return None
    s.expire_all()
    return s.get(RunExecution, cand)


def recover_stale(s: Session, stale_seconds: int = 120) -> int:
    """Re-queue (or fail, after MAX_ATTEMPTS) running jobs whose LEASE expired. Safe to call from many workers at once."""
    now = _now()
    legacy_cutoff = now - timedelta(seconds=stale_seconds)
    expired = or_(
        RunExecution.lease_expires_at < now,
        and_(
            RunExecution.lease_expires_at.is_(None),
            or_(RunExecution.heartbeat_at.is_(None), RunExecution.heartbeat_at < legacy_cutoff),
        ),
    )
    n = 0
    rows = s.execute(
        select(RunExecution.id, RunExecution.attempt).where(RunExecution.status == "running", expired)
    ).all()
    for ex_id, attempt in rows:
        give_up = attempt >= MAX_ATTEMPTS
        vals = (
            {
                "status": "failed",
                "error": "exceeded max attempts after lease expiry",
                "finished_at": now,
                "lease_token": None,
            }
            if give_up
            else {"status": "queued", "lease_token": None, "lease_expires_at": None}
        )
        # compare-and-set: only the recoverer whose UPDATE matches the still-expired row wins
        res = s.execute(
            update(RunExecution)
            .where(RunExecution.id == ex_id, RunExecution.status == "running", expired)
            .values(**vals)
        )
        if getattr(res, "rowcount", 0) == 1:
            n += 1
            if give_up:
                ex = s.get(RunExecution, ex_id)
                run = s.get(Run, ex.run_id) if ex else None
                if run is not None and run.status != "succeeded":
                    run.status, run.error = "failed", "exceeded max attempts after lease expiry"
    s.commit()
    return n


class Lease:
    """Holds a job lease: an independent heartbeat thread (own session) plus an ownership check for fencing."""

    def __init__(self, ex_id: int, token: str, lease_seconds: int, interval: float | None = None):
        self.ex_id, self.token, self.lease_seconds = ex_id, token, lease_seconds
        self.interval = interval if interval is not None else max(0.2, lease_seconds / 4)
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=f"lease-{ex_id}", daemon=True)

    def _beat_once(self) -> bool:
        now = _now()
        with session_scope() as s:  # its OWN session/connection: never shared with the working thread
            res = s.execute(
                update(RunExecution)
                .where(
                    RunExecution.id == self.ex_id,
                    RunExecution.lease_token == self.token,
                    RunExecution.status == "running",
                )
                .values(heartbeat_at=now, lease_expires_at=now + timedelta(seconds=self.lease_seconds))
            )
            return getattr(res, "rowcount", 0) == 1

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                if not self._beat_once():
                    self._lost.set()
                    log.warning("lease lost", extra={"job_id": self.ex_id})
                    return
            except Exception:  # transient DB error: keep trying until the lease actually expires
                log.exception("heartbeat failed", extra={"job_id": self.ex_id})

    def start(self) -> Lease:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def valid(self) -> bool:
        """Fence check: the database still says this worker owns the job."""
        if self._lost.is_set():
            return False
        with session_scope() as s:
            row = s.execute(
                select(RunExecution.lease_token, RunExecution.status).where(RunExecution.id == self.ex_id)
            ).first()
        ok = row is not None and row[0] == self.token and row[1] == "running"
        if not ok:
            self._lost.set()
        return ok


def _finish(ex_id: int, token: str, status: str, error: str | None, run_id: str, run_error: str | None = None) -> bool:
    """Fenced terminal transition: applies only if this worker still holds the lease. Returns whether it applied."""
    with session_scope() as s:
        res = s.execute(
            update(RunExecution)
            .where(RunExecution.id == ex_id, RunExecution.lease_token == token, RunExecution.status == "running")
            .values(status=status, error=error, finished_at=_now(), lease_token=None)
        )
        if getattr(res, "rowcount", 0) != 1:
            return False
        if status == "failed":
            run = s.get(Run, run_id)
            if run is not None:
                run.status, run.error = "failed", run_error or error
        return True


_PATH = _re.compile(r"(/[A-Za-z0-9_.@-]+){2,}")


def _public_error(exc: BaseException) -> str:
    """Run errors are served by public endpoints: redact secrets and strip absolute filesystem paths."""
    return _PATH.sub("<path>", _Redactor().text(f"{type(exc).__name__}: {exc}"))[:500]


def run_job(s: Session, ex: RunExecution, lease_seconds: int = 120, heartbeat_interval: float | None = None) -> None:
    ex_id, run_id, token = ex.id, ex.run_id, ex.lease_token or ""
    run = s.get(Run, run_id)
    assert run is not None
    lease = Lease(ex_id, token, lease_seconds, heartbeat_interval).start()
    try:
        run_svc.execute_run(s, run, owner_check=lease.valid, heartbeat=lambda: None)
        outcome_failed = run.status == "failed"  # e.g. run budget exhausted: evidence incomplete
        # ATOMIC terminal transition: the run row (already flushed, NOT committed) and the job row become final in ONE transaction,
        # and only if this worker still holds the lease. A fenced worker's rowcount is 0 -> everything it did since the last batch
        # commit is rolled back, so it can never leave a "succeeded" run under another attempt's job.
        res = s.execute(
            update(RunExecution)
            .where(RunExecution.id == ex_id, RunExecution.lease_token == token, RunExecution.status == "running")
            .values(
                status="failed" if outcome_failed else "succeeded",
                error=run.error if outcome_failed else None,
                finished_at=_now(),
                lease_token=None,
            )
        )
        if getattr(res, "rowcount", 0) != 1:
            raise run_svc.LeaseLost(f"lost the lease on run {run_id} at completion")
        s.commit()
    except run_svc.LeaseLost as exc:
        s.rollback()
        log.warning("worker fenced: %s", exc, extra={"run_id": run_id, "job_id": ex_id})
        # Not ours any more: another attempt owns the job and the run. Record nothing.
    except Exception as exc:  # job failure is recorded, never silently swallowed
        s.rollback()
        log.exception("job %s failed", ex_id, extra={"run_id": run_id, "job_id": ex_id})
        err = _public_error(exc)
        if not _finish(ex_id, token, "failed", err, run_id):
            log.warning("failure not recorded: lease already lost", extra={"job_id": ex_id})
    finally:
        lease.stop()


def work_once(s: Session, stale_seconds: int = 120) -> bool:
    recover_stale(s, stale_seconds)
    ex = claim_next(s, lease_seconds=stale_seconds)
    if ex is None:
        return False
    log.info("claimed job", extra={"job_id": ex.id, "run_id": ex.run_id})
    run_job(s, ex, lease_seconds=stale_seconds)
    return True
