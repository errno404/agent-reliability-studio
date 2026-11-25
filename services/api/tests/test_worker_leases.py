"""Worker reliability: leases, independent heartbeat, atomic stale recovery, fencing, concurrent claims.

Runs on SQLite always, and on PostgreSQL when ARS_TEST_POSTGRES_URL is set (CI service container / docker compose).
These tests verify a single-database lease. They do NOT claim distributed-consensus safety.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from app import db, seed
from app.models import Base, Run, RunExecution, Sample
from app.services import jobs, runs
from sqlalchemy import func, select, text

PG = os.environ.get("ARS_TEST_POSTGRES_URL")


@pytest.fixture(params=["sqlite"] + (["postgres"] if PG else []))
def engine(request, tmp_path):
    if request.param == "postgres":
        eng = db.reset_engine(PG)
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    else:
        eng = db.reset_engine(f"sqlite:///{tmp_path / 'w.db'}")
    Base.metadata.create_all(eng)
    return eng


def _queue(s, rid="job-1") -> Run:
    cat = seed.seed_catalog(s)
    return runs.create_run(
        s, run_id=rid, name="t", agent_spec="coding:v2", dv=cat["datasets"]["coding/v1"], samples=1, queue=True
    )


def _past(seconds=999):
    return datetime.now(UTC) - timedelta(seconds=seconds)


def test_concurrent_claims_have_exactly_one_winner(engine):
    with db.session_scope() as s:
        _queue(s)
    winners, barrier = [], threading.Barrier(8)

    def go(i):
        with db.session_scope() as s:
            barrier.wait()
            ex = jobs.claim_next(s, f"w{i}")
            if ex is not None:
                winners.append((i, ex.lease_token))

    ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(winners) == 1 and winners[0][1]
    with db.session_scope() as s:
        assert s.scalar(select(RunExecution.attempt)) == 1


def test_concurrent_recovery_requeues_once(engine):
    with db.session_scope() as s:
        _queue(s)
        ex = jobs.claim_next(s)
        ex.lease_expires_at = _past()
        s.commit()
    counts, barrier = [], threading.Barrier(6)

    def go():
        with db.session_scope() as s:
            barrier.wait()
            counts.append(jobs.recover_stale(s, 10))

    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sum(counts) == 1
    with db.session_scope() as s:
        assert s.scalar(select(RunExecution.status)) == "queued"


def test_independent_heartbeat_keeps_a_slow_job_alive(engine):
    """A sample slower than the lease TTL must NOT be recovered while the heartbeat thread is running."""
    with db.session_scope() as s:
        _queue(s)
        ex = jobs.claim_next(s, lease_seconds=1)
        lease = jobs.Lease(ex.id, ex.lease_token or "", lease_seconds=1, interval=0.2).start()
    try:
        time.sleep(2.5)  # > 2x the TTL, with the main thread "blocked in a slow sample"
        with db.session_scope() as s:
            assert jobs.recover_stale(s, 1) == 0
            assert s.scalar(select(RunExecution.status)) == "running"
        assert lease.valid()
    finally:
        lease.stop()


def test_job_without_heartbeat_is_recovered_after_ttl(engine):
    with db.session_scope() as s:
        _queue(s)
        jobs.claim_next(s, lease_seconds=1)
    time.sleep(1.3)
    with db.session_scope() as s:
        assert jobs.recover_stale(s, 1) == 1
        assert s.scalar(select(RunExecution.status)) == "queued"


def test_recovered_job_fences_the_stale_worker(engine):
    """Worker A stalls; B takes over. A's heartbeat/ownership check fails and A can neither write nor complete."""
    with db.session_scope() as s:
        _queue(s)
        a = jobs.claim_next(s, "A", lease_seconds=60)
        a_id, a_token = a.id, a.lease_token or ""
        a.lease_expires_at = _past()
        s.commit()
    with db.session_scope() as s:
        assert jobs.recover_stale(s, 10) == 1
        b = jobs.claim_next(s, "B", lease_seconds=60)
        assert b is not None and b.lease_token != a_token and b.attempt == 2
    lease_a = jobs.Lease(a_id, a_token, 60, interval=0.2)
    assert lease_a.valid() is False  # ownership validated in the database
    assert jobs._finish(a_id, a_token, "succeeded", None, "job-1") is False  # stale worker cannot complete
    with db.session_scope() as s:
        assert s.scalar(select(RunExecution.status)) == "running"  # still B's
        assert s.get(Run, "job-1").status != "succeeded"


def test_fenced_worker_writes_nothing_more(engine):
    with db.session_scope() as s:
        run = _queue(s)
        ex = jobs.claim_next(s)
        alive = {"ok": True}
        calls = {"n": 0}

        def owner_check():
            calls["n"] += 1
            if calls["n"] > 3:
                alive["ok"] = False
            return alive["ok"]

        with pytest.raises(runs.LeaseLost):
            runs.execute_run(s, run, owner_check=owner_check, commit_every=1)
        s.commit()
        assert s.scalar(select(func.count(Sample.id)).where(Sample.run_id == run.id)) == 3  # stopped at the fence
        assert ex.status == "running"


def test_resume_after_takeover_is_idempotent_no_duplicates(engine):
    with db.session_scope() as s:
        run = _queue(s)
        rid = run.id
        jobs.claim_next(s)
        with pytest.raises(runs.LeaseLost):
            runs.execute_run(s, run, owner_check=iter([True] * 4 + [False] * 99).__next__, commit_every=1)
        s.commit()
        s.execute(update_expired())
        s.commit()
    with db.session_scope() as s:
        assert jobs.recover_stale(s, 10) == 1
    with db.session_scope() as s:
        assert jobs.work_once(s) is True
    with db.session_scope() as s:
        assert s.scalar(select(func.count(Sample.id)).where(Sample.run_id == rid)) == 10
        assert s.scalar(select(func.count(func.distinct(Sample.case_id))).where(Sample.run_id == rid)) == 10
        assert s.get(Run, rid).status == "succeeded"
        assert s.scalar(select(RunExecution.status).order_by(RunExecution.id.desc())) == "succeeded"


def update_expired():
    from sqlalchemy import update

    return update(RunExecution).values(lease_expires_at=_past())


def test_attempts_are_bounded(engine):
    with db.session_scope() as s:
        run = _queue(s)
        rid = run.id
        ex = jobs.claim_next(s)
        ex.attempt, ex.lease_expires_at = jobs.MAX_ATTEMPTS, _past()
        s.commit()
    with db.session_scope() as s:
        assert jobs.recover_stale(s, 10) == 1
        assert s.get(Run, rid).status == "failed" and s.scalar(select(RunExecution.status)) == "failed"
        assert jobs.claim_next(s) is None  # never retried again


def test_job_failure_is_fenced_and_recorded_once(engine, monkeypatch):
    with db.session_scope() as s:
        _queue(s)

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(runs, "execute_run", boom)
    with db.session_scope() as s:
        assert jobs.work_once(s) is True
    with db.session_scope() as s:
        assert "provider down" in (s.get(Run, "job-1").error or "")
        assert s.scalar(select(RunExecution.status)) == "failed"
