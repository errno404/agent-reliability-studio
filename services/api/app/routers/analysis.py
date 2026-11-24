"""Overview, comparisons (+ case drill-down), release gates and failure analysis."""

from __future__ import annotations

from typing import Any

from evalcore.models import AgentResult
from evalcore.trajectory import diff_trajectories
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .. import schemas as sc
from ..db import get_session
from ..models import (
    AgentVersion,
    CiGateDecision,
    Comparison,
    EvalCase,
    FailureCluster,
    FailureLabel,
    Run,
    Sample,
)
from ..services import queries
from ..services.comparisons import POLICIES

router = APIRouter(prefix="/api", tags=["analysis"])


def _get_run(s: Session, run_id: str) -> Run:
    r = s.scalar(select(Run).options(*queries.run_options()).where(Run.id == run_id))
    if r is None:
        raise HTTPException(404, "run not found")
    return r


@router.get("/overview")
def overview(s: Session = Depends(get_session)) -> dict[str, Any]:
    pairs = queries.comparisons_with_gates(s)
    if not pairs:
        return {"empty": True}
    gate = s.scalar(select(CiGateDecision).order_by(CiGateDecision.id.desc()).limit(1))
    head, head_gate = next(((c, g) for c, g in pairs if g and gate and g.id == gate.id), pairs[0])
    cand, base = _get_run(s, head.candidate_run_id), _get_run(s, head.baseline_run_id)
    cs, bs = cand.summary, base.summary
    trend = []
    latest = (
        s.scalars(
            select(Run)
            .options(*queries.run_options())
            .where(Run.status == "succeeded", Run.run_type == "synthetic_demo")
            .order_by(Run.created_at, Run.id)
        )
        .unique()
        .all()
    )
    seen: dict[tuple[str, str, str], Run] = {}
    for r in latest:
        if r.judge is not None and r.judge.model != "keyword-strict-v1":
            continue  # diagnostic lenient-judge duplicates are not part of the trend
        if r.dataset_version.version != "v1":
            continue
        seen[(r.agent_version.agent.name, r.agent_version.version, r.dataset_version.dataset.name)] = r
    for (agent, version, _), r in sorted(seen.items()):
        ts = r.summary["task_success"]
        trend.append(
            {
                "agent": agent,
                "version": version,
                "run_id": r.id,
                "rate": ts["rate"],
                "ci_low": ts["ci_low"],
                "ci_high": ts["ci_high"],
                "n": ts["n"],
                "pass_hat_k": r.summary["pass_hat_k"],
                "pass_at_k": r.summary["pass_at_k"],
            }
        )
    ci = queries.comparison_out(head, head_gate)
    return {
        "empty": False,
        "headline": ci.model_dump(mode="json"),
        "baseline": queries.run_out(base).model_dump(mode="json"),
        "candidate": queries.run_out(cand).model_dump(mode="json"),
        "gate": {"verdict": head_gate.verdict, "reasons": head_gate.reasons} if head_gate else None,
        "kpis": {"candidate": cs, "baseline": bs},
        "what_changed": head.result.get("what_changed", ""),
        "category_deltas": head.result.get("category_deltas", {}),
        "trend": trend,
        "failure_categories": queries.clusters_for(s, cand.id),
        "baseline_failure_categories": queries.clusters_for(s, base.id),
        "recent_runs": [
            queries.run_out(r).model_dump(mode="json")
            for r in sorted(latest, key=lambda r: r.created_at, reverse=True)[:6]
        ],
        "totals": {
            "runs": s.scalar(select(func.count(Run.id))),
            "samples": s.scalar(select(func.count(Sample.id))),
            "comparisons": len(pairs),
        },
    }


# ------------------------------------------------------------------ comparisons
@router.get("/comparisons", response_model=list[sc.ComparisonOut])
def list_comparisons(s: Session = Depends(get_session)) -> list[sc.ComparisonOut]:
    return [queries.comparison_out(c, g) for c, g in queries.comparisons_with_gates(s)]


@router.get("/comparisons/{cid}", response_model=sc.ComparisonDetail)
def comparison(cid: int, s: Session = Depends(get_session)) -> sc.ComparisonDetail:
    c = s.get(Comparison, cid)
    if c is None:
        raise HTTPException(404, "comparison not found")
    gate = s.scalar(
        select(CiGateDecision).where(CiGateDecision.comparison_id == cid).order_by(CiGateDecision.id.desc()).limit(1)
    )
    full = next(cc for cc, _ in queries.comparisons_with_gates(s) if cc.id == cid)
    out = queries.comparison_out(full, gate)
    return sc.ComparisonDetail(
        **out.model_dump(),
        validity=c.validity,
        result=c.result,
        baseline=queries.run_out(_get_run(s, c.baseline_run_id)),
        candidate=queries.run_out(_get_run(s, c.candidate_run_id)),
    )


def _samples(s: Session, run_id: str, case_id: str) -> list[Sample]:
    return list(
        s.scalars(
            select(Sample).where(Sample.run_id == run_id, Sample.case_id == case_id).order_by(Sample.sample_index)
        )
    )


@router.get("/comparisons/{cid}/cases/{case_id}", response_model=sc.CaseComparison)
def case_comparison(cid: int, case_id: str, s: Session = Depends(get_session)) -> sc.CaseComparison:
    c = s.get(Comparison, cid)
    if c is None:
        raise HTTPException(404, "comparison not found")
    bs, cs = _samples(s, c.baseline_run_id, case_id), _samples(s, c.candidate_run_id, case_id)
    if not bs and not cs:
        raise HTTPException(404, "case not found in either run")
    cand_run = s.get(Run, c.candidate_run_id)
    case_row = s.scalar(
        select(EvalCase).where(
            EvalCase.dataset_version_id == cand_run.dataset_version_id,  # type: ignore[union-attr]
            EvalCase.case_id == case_id,
        )
    )
    d = case_row.definition if case_row else {}
    diff: dict[str, Any] = {}
    if bs and cs:
        diff = diff_trajectories(AgentResult.model_validate(bs[0].result), AgentResult.model_validate(cs[0].result))
        bd, cd = queries.sample_detail(s, bs[0]), queries.sample_detail(s, cs[0])
        diff["changed_outcome"] = bs[0].status != cs[0].status
        diff["baseline_status"], diff["candidate_status"] = bs[0].status, cs[0].status
        bfail = {a.name for a in bd.assertions if not a.passed and a.gating}
        cfail = {a.name for a in cd.assertions if not a.passed and a.gating}
        diff["assertions_newly_failing"], diff["assertions_fixed"] = sorted(cfail - bfail), sorted(bfail - cfail)
        diff["latency_delta_ms"] = cs[0].latency_ms - bs[0].latency_ms
    return sc.CaseComparison(
        case_id=case_id,
        category=(case_row.category if case_row else (bs or cs)[0].category),
        description=case_row.description if case_row else "",
        expected_assertions=d.get("assertions", []),
        baseline=[queries.sample_detail(s, x) for x in bs],
        candidate=[queries.sample_detail(s, x) for x in cs],
        diff=diff,
    )


# ------------------------------------------------------------------------- gates
@router.get("/gates", response_model=list[sc.GateOut])
def gates(s: Session = Depends(get_session)) -> list[sc.GateOut]:
    out = []
    pairs = {c.id: c for c, _ in queries.comparisons_with_gates(s)}
    for g in s.scalars(select(CiGateDecision).order_by(CiGateDecision.id.desc())):
        c = pairs[g.comparison_id]
        boot = c.result.get("bootstrap") or {}
        out.append(
            sc.GateOut(
                id=g.id,
                comparison_id=c.id,
                comparison_name=c.name,
                verdict=g.verdict,
                reasons=g.reasons,
                judge_ok=g.judge_ok,
                conservative=g.conservative,
                decision=c.decision,
                valid=c.valid,
                explanation=c.explanation,
                policy_name=c.policy_name,
                margin=c.policy.get("margin"),
                ci_low=boot.get("ci_low"),
                ci_high=boot.get("ci_high"),
                delta=boot.get("delta"),
                changed_cases=len(c.result.get("case_changes", [])),
                baseline_run_id=c.baseline_run_id,
                candidate_run_id=c.candidate_run_id,
                created_at=g.created_at,
            )
        )
    return out


@router.get("/policies")
def policies() -> dict[str, Any]:
    return {
        k: {"min_cases": p.min_cases, "alpha": p.alpha, "n_boot": p.n_boot, "margin": p.margin}
        for k, p in POLICIES.items()
    }


# --------------------------------------------------------------------- failures
@router.get("/failures")
def failures(
    run_id: str, baseline_run_id: str | None = None, label: str | None = None, s: Session = Depends(get_session)
) -> dict[str, Any]:
    run = _get_run(s, run_id)
    clusters = queries.clusters_for(s, run_id)
    base = {c["label"]: c for c in queries.clusters_for(s, baseline_run_id)} if baseline_run_id else {}
    items = []
    for c in clusters:
        b = base.get(c["label"])
        row = {
            **c,
            "baseline_count": b["count"] if b else 0,
            "delta": c["count"] - (b["count"] if b else 0),
            "increased": bool(baseline_run_id) and c["count"] > (b["count"] if b else 0),
            "new": bool(baseline_run_id) and not b,
        }
        ids = c["example_sample_ids"][:3]
        smp = s.scalars(select(Sample).where(Sample.id.in_(ids))).all() if ids else []
        labs = queries.labels_by_sample(s, [x.id for x in smp])
        row["examples"] = [queries.sample_out(x, labs.get(x.id, [])).model_dump() for x in smp]
        items.append(row)
    total = sum(c["count"] for c in clusters)
    n_fail = s.scalar(select(func.count(Sample.id)).where(Sample.run_id == run_id, Sample.status == "failed")) or 0
    n_exec = (
        s.scalar(select(func.count(Sample.id)).where(Sample.run_id == run_id, Sample.status == "execution_error")) or 0
    )
    new_or_up = [i for i in items if i["increased"]]
    if baseline_run_id and new_or_up:
        top = sorted(new_or_up, key=lambda i: -i["delta"])[0]
        cats = ", ".join(sorted(top["categories"]))
        summary = (
            f"Failure mode '{top['label']}' increased by {top['delta']} vs the baseline "
            f"({top['baseline_count']} → {top['count']}), concentrated in: {cats}."
        )
    else:
        summary = f"{n_fail} failing samples; top mode: {items[0]['label'] if items else 'none'}."
    return {
        "run": queries.run_out(run).model_dump(mode="json"),
        "n_failed_samples": n_fail,
        "n_execution_errors": n_exec,
        "total_labels": total,
        "clusters": items,
        "summary": summary,
        "note": "Clusters are deterministic counts over stored assertion evidence. "
        "LLM-written clusters (if enabled) are descriptive only and never gate.",
    }


@router.get("/failures/trend")
def failure_trend(agent: str, s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = s.execute(
        select(AgentVersion.version, FailureCluster.label, func.sum(FailureCluster.count))
        .join(Run, Run.agent_version_id == AgentVersion.id)
        .join(FailureCluster, FailureCluster.run_id == Run.id)
        .join(
            AgentVersion.agent.property.mapper.class_,
            AgentVersion.agent_id == AgentVersion.agent.property.mapper.class_.id,
        )
        .where(
            AgentVersion.agent.property.mapper.class_.name == agent,
            Run.run_type == "synthetic_demo",
            Run.judge_config_id.is_(None) | (Run.judge_config_id.is_not(None)),
        )
        .group_by(AgentVersion.version, FailureCluster.label)
    ).all()
    out: dict[str, dict[str, int]] = {}
    for ver, lab, n in rows:
        out.setdefault(ver, {})[lab] = int(n or 0)
    return [{"version": v, "labels": labs} for v, labs in sorted(out.items())]


@router.get("/failures/samples")
def failure_samples(
    run_id: str, label: str, page_size: int = Query(10, le=50), s: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    ids = [
        sid
        for (sid,) in s.execute(
            select(FailureLabel.sample_id)
            .where(FailureLabel.run_id == run_id, FailureLabel.label == label)
            .limit(page_size)
        )
    ]
    rows = s.scalars(select(Sample).where(Sample.id.in_(ids))).all() if ids else []
    labs = queries.labels_by_sample(s, ids)
    return [queries.sample_out(r, labs.get(r.id, [])).model_dump() for r in rows]


_ = joinedload
