"""The published live experiment re-imports cleanly and its comparisons are RECOMPUTED, reproducing the recorded verdict."""

import json

import pytest
from app import experiments
from app.db import session_scope
from app.models import Comparison, Run, Sample
from sqlalchemy import func, select


@pytest.fixture
def imported(fresh_db):
    with session_scope() as s:
        ids = experiments.import_experiment(s)
        s.commit()
    return ids


def test_import_is_complete_and_labelled_live(imported):
    assert sorted(imported) == ["live-dev-v1", "live-dev-v2b", "live-ho-v1", "live-ho-v2"]
    with session_scope() as s:
        for rid in imported:
            r = s.get(Run, rid)
            assert r.run_type == "live" and r.is_synthetic is False
            assert r.manifest["execution_kind"] == "live" and r.manifest["model_resolved"].startswith("claude-")
            n = s.scalar(select(func.count(Sample.id)).where(Sample.run_id == rid))
            assert n == 153 == r.summary["n_samples"]


def test_import_is_idempotent(imported):
    with session_scope() as s:
        assert experiments.import_experiment(s) == []
        assert s.scalar(select(func.count(Comparison.id))) == 2


def test_heldout_comparison_is_recomputed_and_matches_recorded_evidence(imported):
    rec = json.loads((experiments.EXPERIMENT_DIR / "summary.json").read_text())["comparisons"]
    recorded = next(c for c in rec if c["baseline"] == "live-ho-v1")
    with session_scope() as s:
        c = s.scalar(select(Comparison).where(Comparison.baseline_run_id == "live-ho-v1"))
        assert c.valid and c.mode == "strict" and c.result["intent"] == "prompt_change"
        assert c.decision == recorded["decision"] == "no_meaningful_regression"
        b, rb = c.result["bootstrap"], recorded["result"]["bootstrap"]
        assert b["delta"] == pytest.approx(rb["delta"]) and b["ci_low"] == pytest.approx(rb["ci_low"])
        assert (b["n_common_cases"], b["n_improved"], b["n_regressed"]) == (51, 3, 1)
        assert c.result["execution_kind"] == {"baseline": "live", "candidate": "live"}


def test_dev_comparison_is_refused_because_evaluator_hash_drifted(imported):
    """Real provenance catch: the dev baseline ran while evaluator source files were reformatted, so strict mode refuses it."""
    with session_scope() as s:
        c = s.scalar(select(Comparison).where(Comparison.baseline_run_id == "live-dev-v1"))
        assert not c.valid and c.decision == "invalid"
        assert "evaluator" in json.dumps(c.validity)
