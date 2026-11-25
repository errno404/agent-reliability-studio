from datetime import UTC, datetime, timedelta

import pytest
from app import db, seed
from app.models import Run, RunExecution, Sample
from app.services import catalog, jobs, runs
from sqlalchemy import func, select


def _queued_run(s, rid="t-run", samples=1):
    seed_cat = seed.seed_catalog(s)
    dv = seed_cat["datasets"]["coding/v1"]  # 10 cases, quick
    return runs.create_run(
        s, run_id=rid, name="t", agent_spec="redteam:v2" if False else "coding:v2", dv=dv, samples=samples, queue=True
    )


def test_seed_is_idempotent(fresh_db):
    seed.SAMPLES = 1
    with db.session_scope() as s:
        seed.seed_catalog(s)
        n1 = s.scalar(select(func.count(Run.id)))
        seed.seed_catalog(s)
        assert s.scalar(select(func.count(Run.id))) == n1


def test_frozen_dataset_cannot_be_mutated(fresh_db, tmp_path):
    with db.session_scope() as s:
        dv = catalog.sync_dataset(s, "datasets/coding/v1.yaml")
        assert dv.published
        src = (
            (catalog.REPO_ROOT / "datasets/coding/v1.yaml")
            .read_text()
            .replace("Fix slugify punctuation", "Fix slugify PUNCT")
        )
        p = tmp_path / "v1.yaml"
        p.write_text(src)
        with pytest.raises(catalog.FrozenDatasetError):
            catalog.sync_dataset(s, p)


def test_job_claim_run_and_progress(fresh_db):
    with db.session_scope() as s:
        run = _queued_run(s)
        run_id = run.id
        assert run.status == "queued"
    with db.session_scope() as s:
        assert jobs.work_once(s) is True
    with db.session_scope() as s:
        run = s.get(Run, run_id)
        ex = s.scalar(select(RunExecution).where(RunExecution.run_id == run_id))
        assert run.status == "succeeded" and run.progress_done == run.progress_total == 10 and ex.status == "succeeded"
        assert run.summary["task_success"]["n"] > 0
        assert jobs.work_once(s) is False  # queue is drained


def test_claim_is_exclusive(fresh_db):
    with db.session_scope() as s:
        _queued_run(s)
    with db.session_scope() as s1, db.session_scope() as s2:
        a, b = jobs.claim_next(s1, "w1"), jobs.claim_next(s2, "w2")
        assert (a is None) != (b is None)  # exactly one worker wins


def test_stale_job_recovery_and_resume_is_idempotent(fresh_db):
    with db.session_scope() as s:
        run = _queued_run(s, samples=1)
        rid = run.id
        ex = jobs.claim_next(s)
        runs.load_dataset_from_db(s, run.dataset_version)
        # simulate a worker that died after 4 samples
        from demo_agents import get_adapter
        from evalcore import execute_sample

        ds = runs.load_dataset_from_db(s, run.dataset_version)
        adapter = get_adapter("coding:v2")
        for c in ds.cases[:4]:
            runs._persist(s, run, execute_sample(adapter, c, rid, 0, 0), c.input)
        ex.heartbeat_at = datetime.now(UTC) - timedelta(seconds=999)
        ex.lease_expires_at = datetime.now(UTC) - timedelta(seconds=999)
        s.commit()
        assert s.scalar(select(func.count(Sample.id)).where(Sample.run_id == rid)) == 4
    with db.session_scope() as s:
        assert jobs.recover_stale(s, 120) == 1
        assert jobs.recover_stale(s, 120) == 0  # idempotent
    with db.session_scope() as s:
        assert jobs.work_once(s) is True
    with db.session_scope() as s:
        assert s.scalar(select(func.count(Sample.id)).where(Sample.run_id == rid)) == 10  # no duplicates
        assert s.get(Run, rid).status == "succeeded"


def test_job_failure_is_recorded_not_swallowed(fresh_db, monkeypatch):
    with db.session_scope() as s:
        _queued_run(s)

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(runs, "execute_run", boom)
    with db.session_scope() as s:
        jobs.work_once(s)
    with db.session_scope() as s:
        run = s.scalar(select(Run))
        ex = s.scalar(select(RunExecution))
        assert run.status == "failed" and "disk full" in (run.error or "") and ex.status == "failed"


def test_stale_job_gives_up_after_max_attempts(fresh_db):
    with db.session_scope() as s:
        run = _queued_run(s)
        ex = jobs.claim_next(s)
        ex.attempt, ex.lease_expires_at = jobs.MAX_ATTEMPTS, datetime.now(UTC) - timedelta(seconds=999)
        s.commit()
        rid = run.id
    with db.session_scope() as s:
        jobs.recover_stale(s, 10)
        assert s.get(Run, rid).status == "failed"
