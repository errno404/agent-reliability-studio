"""Create, execute and persist evaluation runs. The worker, CLI and seed all use these functions."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from demo_agents import agent_info, get_adapter
from evalcore import RunManifest, SampleResult, SampleStatus, execute_sample, summarize
from evalcore.hashing import hash_obj
from evalcore.models import AgentResult, AssertionResult, Case, Dataset
from evalcore.pricing import SYNTHETIC_PRICES
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    AgentVersion,
    AssertionResultRow,
    DatasetVersion,
    EvalCase,
    FailureCluster,
    FailureLabel,
    Run,
    RunExecution,
    Sample,
    SpanRow,
)
from ..models import (
    JudgeConfig as JudgeRow,
)
from . import judges
from .catalog import git_info

log = logging.getLogger("ars.runs")

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def load_dataset_from_db(s: Session, dv: DatasetVersion) -> Dataset:
    """Rebuild the dataset from the stored (frozen) case definitions, then verify its hash."""
    from evalcore import dataset_hash

    rows = s.scalars(select(EvalCase).where(EvalCase.dataset_version_id == dv.id).order_by(EvalCase.id)).all()
    ds = Dataset(
        name=dv.dataset.name,
        version=dv.version,
        kind=dv.dataset.kind,
        published=dv.published,
        fixture_version=dv.fixture_version,
        cases=[Case.model_validate(r.definition) for r in rows],
    )
    got = dataset_hash(ds)
    if got != dv.hash:
        raise RuntimeError(f"stored cases for {dv.dataset.name}:{dv.version} hash to {got}, expected {dv.hash}")
    return ds


def build_manifest(
    run_id: str,
    run_type: str,
    av: AgentVersion,
    dv: DatasetVersion,
    ds: Dataset,
    samples: int,
    seed: int,
    judge: JudgeRow | None,
    concurrency: int = 1,
) -> RunManifest:
    sha, dirty = git_info()
    return RunManifest(
        run_id=run_id,
        run_type=run_type,
        agent=av.agent.name,
        agent_version=av.version,
        agent_hash=av.agent_hash,
        dataset_name=dv.dataset.name,
        dataset_path=dv.source_path,
        dataset_hash=dv.hash,
        fixture_hash=dv.fixture_hash,
        case_ids=[c.id for c in ds.cases],
        samples_per_case=samples,
        model_provider="synthetic",
        model=av.model,
        model_params={"temperature": 0, "seed": seed},
        judge_backend=judge.backend if judge else "",
        judge_model=judge.model if judge else "",
        judge_prompt_hash=judge.prompt_hash if judge else "",
        tool_schema_hash=av.tool_schema_hash,
        git_commit=sha,
        git_dirty=dirty,
        concurrency=concurrency,
        seed=seed,
    )


def create_run(
    s: Session,
    *,
    run_id: str,
    name: str,
    agent_spec: str,
    dv: DatasetVersion,
    samples: int = 1,
    seed: int = 0,
    run_type: str = "synthetic_demo",
    judge: JudgeRow | None = None,
    queue: bool = True,
) -> Run:
    existing = s.get(Run, run_id)
    if existing is not None:
        return existing
    from .catalog import sync_agent_version

    av = sync_agent_version(s, agent_spec)
    ds = load_dataset_from_db(s, dv)
    man = build_manifest(run_id, run_type, av, dv, ds, samples, seed, judge)
    run = Run(
        id=run_id,
        name=name,
        run_type=run_type,
        status="queued",
        agent_version_id=av.id,
        dataset_version_id=dv.id,
        judge_config_id=judge.id if judge else None,
        samples_per_case=samples,
        seed=seed,
        manifest=man.to_dict(),
        manifest_hash=man.content_hash(),
        progress_total=len(ds.cases) * samples,
        is_synthetic=run_type == "synthetic_demo",
    )
    s.add(run)
    s.flush()
    if queue:
        s.add(RunExecution(run_id=run.id, status="queued"))
    s.flush()
    return run


def _persist(s: Session, run: Run, smp: SampleResult, input_text: str) -> Sample:
    res = smp.result
    trace_id = res.spans[0].trace_id if res.spans else ""
    row = Sample(
        run_id=run.id,
        case_id=smp.case_id,
        category=smp.category,
        sample_index=smp.sample_index,
        status=smp.status.value,
        error_kind=res.error_kind,
        input_text=input_text,
        final_output=res.final_output,
        tool_sequence=res.tool_names,
        latency_ms=res.latency_ms,
        input_tokens=res.input_tokens,
        output_tokens=res.output_tokens,
        cost_usd=res.cost_usd,
        turns=res.turns,
        steps=res.steps,
        result=json.loads(res.model_dump_json(exclude={"spans"})),
        judge=smp.judge,
        seed=smp.seed,
        trace_id=trace_id,
    )
    s.add(row)
    s.flush()
    for a in smp.assertions:
        s.add(
            AssertionResultRow(
                sample_id=row.id,
                name=a.name,
                type=a.type,
                layer=a.layer.value,
                gating=a.gating,
                passed=a.passed,
                skipped=a.skipped,
                invalid=a.invalid,
                severity=a.severity.value,
                expected=a.expected,
                actual=a.actual,
                evidence=a.evidence,
                label=a.label,
            )
        )
    for sp in res.spans:
        s.add(
            SpanRow(
                sample_id=row.id,
                trace_id=sp.trace_id,
                span_id=sp.span_id,
                parent_id=sp.parent_id,
                name=sp.name,
                kind=sp.kind,
                start_ms=sp.start_ms,
                duration_ms=sp.duration_ms,
                status=sp.status,
                attributes=sp.attributes,
            )
        )
    for lab in smp.failure_labels:
        s.add(FailureLabel(sample_id=row.id, run_id=run.id, label=lab))
    return row


def execute_run(
    s: Session,
    run: Run,
    on_progress: Callable[[int, int], None] | None = None,
    heartbeat: Callable[[], None] | None = None,
    commit_every: int = 10,
) -> None:
    """Execute every missing (case, sample_index). Idempotent: existing samples are skipped (resume-safe)."""
    dv = run.dataset_version
    ds = load_dataset_from_db(s, dv)
    spec = f"{run.agent_version.agent.name}:{run.agent_version.version}"
    adapter = get_adapter(spec)
    judge = judge_admitted = None
    if run.judge is not None:
        judge, judge_admitted = judges.build_judge(run.judge), judges.judge_admitted(s, run.judge_config_id)
        run.judge_admitted = bool(judge_admitted)
    done = {(c, i) for c, i in s.execute(select(Sample.case_id, Sample.sample_index).where(Sample.run_id == run.id))}
    run.status = "running"
    total = len(ds.cases) * run.samples_per_case
    run.progress_total = total
    n = len(done)
    for case in ds.cases:
        for i in range(run.samples_per_case):
            if (case.id, i) in done:
                continue
            smp = execute_sample(adapter, case, run.id, i, run.seed, SYNTHETIC_PRICES, judge, bool(judge_admitted))
            _persist(s, run, smp, case.input)
            n += 1
            run.progress_done = n
            if n % commit_every == 0:
                s.commit()
                if heartbeat:
                    heartbeat()
                if on_progress:
                    on_progress(n, total)
    s.flush()
    finalize_run(s, run)


def load_samples(s: Session, run_id: str) -> list[SampleResult]:
    """Rebuild evalcore SampleResult objects from persisted rows (no spans needed for statistics)."""
    from evalcore.models import Layer, Severity

    out: list[SampleResult] = []
    rows = s.scalars(select(Sample).where(Sample.run_id == run_id).order_by(Sample.case_id, Sample.sample_index)).all()
    ids = [r.id for r in rows]
    by_sample: dict[int, list[AssertionResultRow]] = {}
    if ids:
        for a in s.scalars(select(AssertionResultRow).where(AssertionResultRow.sample_id.in_(ids))):
            by_sample.setdefault(a.sample_id, []).append(a)
    labels: dict[int, list[str]] = {}
    for fl in s.scalars(select(FailureLabel).where(FailureLabel.run_id == run_id)):
        labels.setdefault(fl.sample_id, []).append(fl.label)
    for r in rows:
        ars = [
            AssertionResult(
                name=a.name,
                type=a.type,
                layer=Layer(a.layer),
                gating=a.gating,
                passed=a.passed,
                expected=a.expected,
                actual=a.actual,
                evidence=a.evidence,
                severity=Severity(a.severity),
                invalid=a.invalid,
                skipped=a.skipped,
                label=a.label,
            )
            for a in by_sample.get(r.id, [])
        ]
        out.append(
            SampleResult(
                case_id=r.case_id,
                category=r.category,
                sample_index=r.sample_index,
                status=SampleStatus(r.status),
                assertions=ars,
                result=AgentResult.model_validate(r.result),
                failure_labels=labels.get(r.id, []),
                judge=r.judge,
                seed=r.seed,
            )
        )
    return out


def finalize_run(s: Session, run: Run) -> None:
    samples = load_samples(s, run.id)
    run.summary = _json_safe(summarize(samples))
    run.progress_done = len(samples)
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    compute_clusters(s, run)
    s.flush()


def _json_safe(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


def compute_clusters(s: Session, run: Run) -> None:
    """Deterministic failure clusters (counts, severity, categories, examples). LLM clustering is descriptive only."""
    s.execute(delete(FailureCluster).where(FailureCluster.run_id == run.id, FailureCluster.source == "deterministic"))
    rows = s.execute(
        select(FailureLabel.label, Sample.id, Sample.case_id, Sample.category)
        .join(Sample, FailureLabel.sample_id == Sample.id)
        .where(FailureLabel.run_id == run.id)
    ).all()
    if not rows:
        return
    sev_by_sample: dict[int, str] = {}
    for sid, sev in s.execute(
        select(AssertionResultRow.sample_id, AssertionResultRow.severity)
        .join(Sample, AssertionResultRow.sample_id == Sample.id)
        .where(Sample.run_id == run.id, AssertionResultRow.passed.is_(False), AssertionResultRow.gating.is_(True))
    ):
        if SEVERITY_ORDER[sev] >= SEVERITY_ORDER[sev_by_sample.get(sid, "low")]:
            sev_by_sample[sid] = sev
    total = len(rows)
    groups: dict[str, list[tuple[int, str, str]]] = {}
    for label, sid, case_id, cat in rows:
        groups.setdefault(label, []).append((sid, case_id, cat))
    for label, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        cats = Counter(c for _, _, c in items)
        sev = max((sev_by_sample.get(sid, "medium") for sid, _, _ in items), key=lambda x: SEVERITY_ORDER[x])
        cases = sorted({cid for _, cid, _ in items})
        s.add(
            FailureCluster(
                run_id=run.id,
                label=label,
                count=len(items),
                pct_of_failures=round(len(items) / total, 4),
                severity=sev,
                categories=dict(cats),
                example_sample_ids=[sid for sid, _, _ in items[:5]],
                summary=f"{len(items)} failing sample(s) across {len(cases)} case(s) in {', '.join(sorted(cats))} "
                f"(e.g. {', '.join(cases[:3])}).",
            )
        )


def agent_spec(run: Run) -> str:
    return f"{run.agent_version.agent.name}:{run.agent_version.version}"


def pinned_identity(run: Run) -> dict[str, Any]:
    info = agent_info(agent_spec(run))
    return {
        **info,
        "stored_agent_hash": run.agent_version.agent_hash,
        "matches": info["agent_hash"] == run.agent_version.agent_hash,
    }


def hash_of(obj: Any) -> str:
    return hash_obj(obj, 12)
