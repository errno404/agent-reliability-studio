"""Import PUBLISHED live-experiment evidence (sanitized, re-importable) into the database.

The evidence bundle holds real measurements; nothing is generated here. Comparisons are NOT copied: they are RECOMPUTED
from
the imported samples by the same evaluator code, so the dashboard can never show a stored number that the code would not
reproduce. Imported runs carry ``run_type="live"`` and ``is_synthetic=False``.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from evalcore.redaction import Redactor
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AssertionResultRow, FailureLabel, Run, Sample, SpanRow
from .services import catalog, comparisons

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = ROOT / "evidence/experiments/001-research-agent-reliability"
DATASETS = ("datasets/research-live/dev-v1.yaml", "datasets/research-live/heldout-v1.yaml")
# (baseline, candidate, label) pairs recomputed after import
COMPARISONS = (("live-ho-v1", "live-ho-v2", "held-out"), ("live-dev-v1", "live-dev-v2b", "dev"))


def import_experiment(s: Session, directory: Path = EXPERIMENT_DIR) -> list[str]:
    bundle = directory / "runs.jsonl.gz"
    if not bundle.exists():
        return []
    rd = Redactor()
    for p in DATASETS:
        catalog.sync_dataset(s, p)
    done: list[str] = []
    with gzip.open(bundle, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            r: dict[str, Any] = rec["run"]
            if s.get(Run, r["id"]) is not None:
                continue
            m = r["manifest"]
            av = catalog.sync_agent_version(s, m["agent_config"]["spec"])
            dv = catalog.sync_dataset(s, f"datasets/research-live/{'dev' if 'dev' in r['id'] else 'heldout'}-v1.yaml")
            if dv.hash != m["dataset_hash"]:
                raise ValueError(f"{r['id']}: dataset on disk ({dv.hash}) differs from the measured one")
            run = Run(
                id=r["id"],
                name=r["name"],
                run_type="live",
                status=r["status"],
                agent_version_id=av.id,
                dataset_version_id=dv.id,
                judge_admitted=False,
                samples_per_case=r["samples_per_case"],
                seed=r["seed"],
                manifest=m,
                manifest_hash=r["manifest_hash"],
                summary=r["summary"],
                progress_done=len(rec["samples"]),
                progress_total=len(rec["samples"]),
                is_synthetic=False,
                created_at=datetime.fromisoformat(r["created_at"]),
                finished_at=datetime.fromisoformat(r["finished_at"]) if r["finished_at"] else None,
            )
            s.add(run)
            s.flush()
            for sm in rec["samples"]:
                sm = rd.apply(sm)
                row = Sample(
                    run_id=run.id,
                    **{
                        k: sm[k]
                        for k in (
                            "case_id",
                            "category",
                            "sample_index",
                            "status",
                            "error_kind",
                            "input_text",
                            "final_output",
                            "tool_sequence",
                            "latency_ms",
                            "input_tokens",
                            "output_tokens",
                            "cost_usd",
                            "turns",
                            "steps",
                            "result",
                            "judge",
                            "seed",
                            "trace_id",
                        )
                    },
                )
                s.add(row)
                s.flush()
                s.add_all(AssertionResultRow(sample_id=row.id, **a) for a in sm["assertions"])
                s.add_all(SpanRow(sample_id=row.id, **sp) for sp in sm["spans"])
                s.add_all(FailureLabel(sample_id=row.id, run_id=run.id, label=lab) for lab in sm["labels"])
            done.append(run.id)
    s.flush()
    for base, cand, label in COMPARISONS:
        if s.get(Run, base) and s.get(Run, cand):
            existing = s.scalar(
                select(comparisons.Comparison).where(
                    comparisons.Comparison.baseline_run_id == base, comparisons.Comparison.candidate_run_id == cand
                )
            )
            if existing is None:
                comparisons.create_comparison(
                    s,
                    base,
                    cand,
                    mode="strict",
                    policy_name="production",
                    name=f"research-live v1 -> v2 ({label})",
                    intent="prompt_change",
                )
    return done
