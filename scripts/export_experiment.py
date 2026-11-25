#!/usr/bin/env python3
"""Export a finished LIVE experiment from a database as sanitized, machine-readable, re-importable evidence.

Output (``--out``): ``runs.jsonl.gz`` (one line per run: manifest + summary + every sample with assertions, spans, labels),
``summary.json`` (human-scale metrics + the stored comparison decisions) and ``README.md``.
Everything was redacted before it was stored; it is redacted again here. Nothing is added, dropped or edited by hand.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("packages/evalcore/src", "packages/demo_agents", "mcp/fixture_web", "services/api"):
    sys.path.insert(0, str(ROOT / p))


def export(db_url: str, run_ids: list[str], out: Path) -> None:
    from app.db import reset_engine, session_scope
    from app.models import Comparison, Run, Sample
    from evalcore.redaction import Redactor
    from sqlalchemy import select

    rd = Redactor()
    reset_engine(db_url)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"runs": {}, "comparisons": []}
    with session_scope() as s, gzip.open(out / "runs.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
        for rid in run_ids:
            r = s.get(Run, rid)
            assert r is not None, rid
            smps = []
            for sm in s.scalars(
                select(Sample).where(Sample.run_id == rid).order_by(Sample.case_id, Sample.sample_index)
            ):
                smps.append(
                    rd.apply(
                        {
                            "case_id": sm.case_id,
                            "category": sm.category,
                            "sample_index": sm.sample_index,
                            "status": sm.status,
                            "error_kind": sm.error_kind,
                            "input_text": sm.input_text,
                            "final_output": sm.final_output,
                            "tool_sequence": sm.tool_sequence,
                            "latency_ms": sm.latency_ms,
                            "input_tokens": sm.input_tokens,
                            "output_tokens": sm.output_tokens,
                            "cost_usd": sm.cost_usd,
                            "turns": sm.turns,
                            "steps": sm.steps,
                            "result": sm.result,
                            "judge": sm.judge,
                            "seed": sm.seed,
                            "trace_id": sm.trace_id,
                            "assertions": [
                                {
                                    c: getattr(a, c)
                                    for c in (
                                        "name",
                                        "type",
                                        "layer",
                                        "gating",
                                        "passed",
                                        "skipped",
                                        "invalid",
                                        "severity",
                                        "expected",
                                        "actual",
                                        "evidence",
                                        "label",
                                    )
                                }
                                for a in sm.assertions
                            ],
                            "spans": [
                                {
                                    c: getattr(sp, c)
                                    for c in (
                                        "trace_id",
                                        "span_id",
                                        "parent_id",
                                        "name",
                                        "kind",
                                        "start_ms",
                                        "duration_ms",
                                        "status",
                                        "attributes",
                                    )
                                }
                                for sp in sm.spans
                            ],
                            "labels": [lab.label for lab in sm.labels],
                        }
                    )
                )
            run = {
                "id": r.id,
                "name": r.name,
                "run_type": r.run_type,
                "status": r.status,
                "samples_per_case": r.samples_per_case,
                "seed": r.seed,
                "manifest": r.manifest,
                "manifest_hash": r.manifest_hash,
                "summary": r.summary,
                "is_synthetic": r.is_synthetic,
                "created_at": r.created_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            fh.write(json.dumps({"run": run, "samples": smps}, sort_keys=True, default=str) + "\n")
            summary["runs"][rid] = {
                "name": r.name,
                "manifest": {
                    k: r.manifest.get(k)
                    for k in (
                        "agent",
                        "agent_version",
                        "agent_hash",
                        "model",
                        "model_resolved",
                        "execution_kind",
                        "dataset_name",
                        "dataset_version",
                        "dataset_hash",
                        "fixture_hash",
                        "samples_per_case",
                        "evaluator_hash",
                        "agent_config",
                    )
                },
                "summary": r.summary,
            }
        for c in s.scalars(select(Comparison).where(Comparison.baseline_run_id.in_(run_ids))):
            summary["comparisons"].append(
                {
                    "name": c.name,
                    "baseline": c.baseline_run_id,
                    "candidate": c.candidate_run_id,
                    "mode": c.mode,
                    "policy": c.policy_name,
                    "decision": c.decision,
                    "valid": c.valid,
                    "explanation": c.explanation,
                    "result": c.result,
                }
            )
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    export(a.db, a.runs, a.out)
    print(f"exported {len(a.runs)} runs to {a.out}")
