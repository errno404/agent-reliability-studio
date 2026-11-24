"""Read-side serializers/aggregations. One query per page; no per-row lookups (no N+1)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .. import schemas as sc
from ..models import (
    AssertionResultRow,
    CiGateDecision,
    Comparison,
    DatasetVersion,
    EvalCase,
    FailureCluster,
    Run,
    Sample,
)

STATUS_EXPLAIN = {
    "passed": "Every gating assertion passed.",
    "failed": "One or more gating assertions failed (an agent quality failure).",
    "execution_error": "The run itself broke (infrastructure/provider/adapter). "
    "This is NOT counted as a quality failure.",
    "invalid": "An assertion spec was malformed, so the sample could not be judged.",
    "skipped": "No gating assertion could be evaluated.",
}


def run_options() -> list[Any]:
    return [
        joinedload(Run.agent_version).joinedload(
            __import__("app.models", fromlist=["AgentVersion"]).AgentVersion.agent
        ),
        joinedload(Run.dataset_version).joinedload(DatasetVersion.dataset),
        joinedload(Run.judge),
    ]


def run_out(r: Run) -> sc.RunOut:
    ts = (r.summary or {}).get("task_success") or {}
    return sc.RunOut(
        id=r.id,
        name=r.name,
        run_type=r.run_type,
        status=r.status,
        agent=r.agent_version.agent.name,
        agent_version=r.agent_version.version,
        model=r.agent_version.model,
        dataset=r.dataset_version.dataset.name,
        dataset_version=r.dataset_version.version,
        dataset_hash=r.dataset_version.hash,
        samples_per_case=r.samples_per_case,
        seed=r.seed,
        judge=r.judge.model if r.judge else None,
        judge_admitted=r.judge_admitted,
        git_commit=(r.manifest or {}).get("git_commit", ""),
        pass_rate=ts.get("rate"),
        pass_ci=[ts["ci_low"], ts["ci_high"]] if ts.get("rate") is not None else None,
        n_cases=(r.summary or {}).get("n_cases", 0),
        n_samples=(r.summary or {}).get("n_samples", 0),
        cost_usd=(r.summary or {}).get("cost_usd"),
        cost_label=(r.summary or {}).get("cost_label", "pricing unavailable"),
        p95_latency_ms=(r.summary or {}).get("latency_p95_ms", 0.0),
        progress_done=r.progress_done,
        progress_total=r.progress_total,
        is_synthetic=r.is_synthetic,
        created_at=r.created_at,
        error=r.error,
    )


def clusters_for(s: Session, run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "label": c.label,
            "count": c.count,
            "pct_of_failures": c.pct_of_failures,
            "severity": c.severity,
            "categories": c.categories,
            "example_sample_ids": c.example_sample_ids,
            "summary": c.summary,
            "source": c.source,
        }
        for c in s.scalars(
            select(FailureCluster).where(FailureCluster.run_id == run_id).order_by(FailureCluster.count.desc())
        )
    ]


def sample_out(smp: Sample, labels: list[str]) -> sc.SampleOut:
    return sc.SampleOut(
        id=smp.id,
        run_id=smp.run_id,
        case_id=smp.case_id,
        category=smp.category,
        sample_index=smp.sample_index,
        status=smp.status,
        error_kind=smp.error_kind,
        tool_sequence=list(smp.tool_sequence or []),
        latency_ms=smp.latency_ms,
        total_tokens=smp.input_tokens + smp.output_tokens,
        cost_usd=smp.cost_usd,
        failure_labels=labels,
        trace_id=smp.trace_id,
        final_output_preview=(smp.final_output or "")[:160],
    )


def labels_by_sample(s: Session, sample_ids: list[int]) -> dict[int, list[str]]:
    from ..models import FailureLabel

    out: dict[int, list[str]] = {}
    if sample_ids:
        for sid, lab in s.execute(
            select(FailureLabel.sample_id, FailureLabel.label).where(FailureLabel.sample_id.in_(sample_ids))
        ):
            out.setdefault(sid, []).append(lab)
    return out


def sample_detail(s: Session, smp: Sample) -> sc.SampleDetail:
    asserts = s.scalars(
        select(AssertionResultRow).where(AssertionResultRow.sample_id == smp.id).order_by(AssertionResultRow.id)
    ).all()
    base = sample_out(smp, labels_by_sample(s, [smp.id]).get(smp.id, []))
    return sc.SampleDetail(
        **base.model_dump(),
        input_text=smp.input_text,
        final_output=smp.final_output,
        result={k: v for k, v in smp.result.items() if k not in ("messages",)},
        judge=smp.judge,
        assertions=[sc.AssertionOut.model_validate(a) for a in asserts],
        status_explanation=STATUS_EXPLAIN.get(smp.status, ""),
    )


def comparison_out(c: Comparison, gate: CiGateDecision | None) -> sc.ComparisonOut:
    boot = (c.result or {}).get("bootstrap") or {}
    b, cd = c.baseline_run, c.candidate_run
    lab = lambda r: f"{r.agent_version.agent.name}:{r.agent_version.version}"  # noqa: E731
    return sc.ComparisonOut(
        id=c.id,
        name=c.name,
        baseline_run_id=c.baseline_run_id,
        candidate_run_id=c.candidate_run_id,
        baseline_label=lab(b),
        candidate_label=lab(cd),
        mode=c.mode,
        policy_name=c.policy_name,
        policy=c.policy,
        decision=c.decision,
        valid=c.valid,
        explanation=c.explanation,
        delta=boot.get("delta"),
        ci_low=boot.get("ci_low"),
        ci_high=boot.get("ci_high"),
        margin=c.policy.get("margin"),
        n_common_cases=boot.get("n_common_cases", 0),
        gate_verdict=gate.verdict if gate else None,
        created_at=c.created_at,
    )


def comparisons_with_gates(s: Session, limit: int | None = None) -> list[tuple[Comparison, CiGateDecision | None]]:
    q = (
        select(Comparison)
        .options(
            joinedload(Comparison.baseline_run)
            .joinedload(Run.agent_version)
            .joinedload(__import__("app.models", fromlist=["AgentVersion"]).AgentVersion.agent),
            joinedload(Comparison.candidate_run)
            .joinedload(Run.agent_version)
            .joinedload(__import__("app.models", fromlist=["AgentVersion"]).AgentVersion.agent),
        )
        .order_by(Comparison.id.desc())
    )
    if limit:
        q = q.limit(limit)
    comps = s.scalars(q).unique().all()
    gates = {g.comparison_id: g for g in s.scalars(select(CiGateDecision).order_by(CiGateDecision.id))}
    return [(c, gates.get(c.id)) for c in comps]


def dataset_categories(s: Session, dv_id: int) -> dict[str, int]:
    return dict(
        s.execute(
            select(EvalCase.category, func.count())
            .where(EvalCase.dataset_version_id == dv_id)
            .group_by(EvalCase.category)
        ).all()
    )


def status_counts(s: Session, run_id: str) -> dict[str, int]:
    return dict(
        Counter(
            {
                k: v
                for k, v in s.execute(
                    select(Sample.status, func.count()).where(Sample.run_id == run_id).group_by(Sample.status)
                ).all()
            }
        )
    )
