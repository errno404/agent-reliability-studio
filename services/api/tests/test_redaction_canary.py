"""End-to-end canary: secrets planted in EVERY agent-influenced field must not appear in ANY table, API response or export.

An adapter returns canaries in its output, tool arguments/results, span attributes, error text, messages and state. The run goes
through the real service pipeline (execute_run -> _persist); then every column of every table, every read endpoint and the
distillation output are scanned. Structural types and numerics must survive redaction.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from app import seed
from app.models import Base, Run, Sample
from app.services import runs
from evalcore.distill import distill_case
from evalcore.models import AgentResult, Case, SpanRecord, ToolCall
from evalcore.redaction import Redactor
from fastapi.testclient import TestClient
from sqlalchemy import select

CANARIES = [
    "DEMO_SECRET_DO_NOT_REVEAL_7F2A",
    "sk-ant-api03-CANARYCANARYCANARY0123456789",
    "ghp_CANARYCANARYCANARYCANARY0123456789",
    "eyJCANARYHEAD0123.eyJCANARYBODY0123.CANARYSIG0123",
    "AKIACANARYCANARY1234",
    "postgres://svcuser:CANARYPASSWORD99@db.internal/prod",
    "Bearer CANARYTOKENCANARYTOKEN0123",
]
BAD = CANARIES + ["CANARYPASSWORD99", "CANARYTOKENCANARYTOKEN0123"]


class Leaky:
    """Plants every canary everywhere an agent can influence stored data."""

    def __init__(self, inner):
        self.inner, self.name, self.version = inner, inner.name, inner.version
        self.model = getattr(inner, "model", "m")
        self.agent_hash = inner.agent_hash
        self.prompt_hash = inner.prompt_hash

    def run(self, case, ctx):
        c = " | ".join(CANARIES)
        return AgentResult(
            final_output=f"the secret is {c}",
            tool_calls=[
                ToolCall(
                    name="lookup",
                    arguments={"api_key": CANARIES[1], "q": f"find {CANARIES[0]}", "limit": 5, "flag": True},
                    result={"leak": c, "n": 3, "rows": [{"token": CANARIES[2]}]},
                    error=f"upstream said {CANARIES[5]}",
                )
            ],
            messages=[{"role": "tool", "content": c}],
            state={"password": CANARIES[3], "balance": 12.5},
            spans=[
                SpanRecord(
                    span_id="s1",
                    trace_id="t1",
                    name="tool:lookup",
                    kind="tool",
                    attributes={"gen_ai.tool.call.arguments": c, "authorization": CANARIES[6], "count": 3},
                )
            ],
            input_tokens=11,
            output_tokens=7,
            latency_ms=12.5,
            metadata={"note": c},
        )


@pytest.fixture
def leaky_run(fresh_db, monkeypatch):
    from app.db import session_scope

    real = runs.resolve

    def patched(spec):
        r = real(spec)
        return dataclasses.replace(r, adapter=Leaky(r.adapter))

    monkeypatch.setattr(runs, "resolve", patched)
    with session_scope() as s:
        cat = seed.seed_catalog(s)
        run = runs.create_run(
            s,
            run_id="canary",
            name="c",
            agent_spec="support:v1",
            dv=cat["datasets"]["support/v1"],
            samples=1,
            queue=False,
        )
        runs.execute_run(s, run)
        s.commit()
    return "canary"


def _all_text(engine) -> list[tuple[str, str]]:
    out = []
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            for row in conn.execute(table.select()):
                for col, val in row._mapping.items():
                    out.append(
                        (f"{table.name}.{col}", json.dumps(val, default=str) if not isinstance(val, str) else val)
                    )
    return out


def test_no_canary_in_any_table_column(leaky_run, fresh_db):
    # Dataset DEFINITIONS legitimately carry the synthetic secret as the thing to detect; everything else must be clean.
    definitions = ("eval_cases.", "dataset_versions.", "calibration_items.")
    leaks = sorted(
        {
            (where, c)
            for where, text in _all_text(fresh_db)
            for c in BAD
            if c in text and not (c == CANARIES[0] and where.startswith(definitions))
        }
    )
    assert leaks == []


def test_pipeline_really_ran_and_structure_survives(leaky_run):
    from app.db import session_scope

    with session_scope() as s:
        smp = s.scalars(select(Sample).where(Sample.run_id == leaky_run)).first()
        assert smp is not None and smp.input_tokens == 11 and smp.latency_ms == 12.5
        call = smp.result["tool_calls"][0]
        assert call["arguments"]["limit"] == 5 and call["arguments"]["flag"] is True  # numerics/bools kept
        assert call["result"]["n"] == 3 and smp.result["state"]["balance"] == 12.5
        assert "[REDACTED" in json.dumps(smp.result)  # and redaction actually happened


def test_no_canary_in_api_responses(leaky_run, fresh_db):
    from app.db import session_scope
    from app.main import app

    client = TestClient(app)
    with session_scope() as s:
        sid = s.scalars(select(Sample.id).where(Sample.run_id == leaky_run)).first()
    urls = [
        f"/api/runs/{leaky_run}",
        f"/api/runs/{leaky_run}/samples",
        f"/api/samples/{sid}",
        f"/api/samples/{sid}/trace",
        "/api/traces",
        "/api/runs",
        "/api/candidates",
        "/api/meta",
    ]
    for u in urls:
        r = client.get(u)
        assert r.status_code == 200, u
        assert not [c for c in BAD if c in r.text], u


def test_distilled_candidates_are_redacted(leaky_run):
    from app.db import session_scope
    from app.models import EvalCase

    with session_scope() as s:
        run = s.get(Run, leaky_run)
        smp = s.scalars(select(Sample).where(Sample.run_id == leaky_run)).first()
        row = s.scalars(select(EvalCase).where(EvalCase.dataset_version_id == run.dataset_version_id)).first()
        cand = distill_case(
            Case.model_validate(row.definition), AgentResult.model_validate(smp.result), leaky_run, 0, False
        )
    text = json.dumps(Redactor().apply(cand))
    assert not [c for c in BAD if c in text]


def test_raw_unredacted_result_would_have_leaked(leaky_run):
    """Guard against a vacuous test: the planted canaries really are in the raw adapter output."""
    raw = Leaky(type("A", (), {"name": "a", "version": "v", "agent_hash": "h", "prompt_hash": "p"})()).run(None, None)
    assert all(c in raw.model_dump_json() for c in CANARIES)
