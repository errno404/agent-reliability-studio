"""Create, execute and persist evaluation runs. The worker, CLI and seed all use these functions."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from evalcore import RunManifest, SampleResult, SampleStatus, execute_sample, summarize
from evalcore.hashing import hash_obj
from evalcore.models import AgentResult, AssertionResult, Case, Dataset
from evalcore.redaction import Redactor
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
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
from ..registry import ResolvedAgent, resolve
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


class LeaseLost(RuntimeError):
    """This worker no longer owns the job (a stale-recovery handed it to someone else); it must stop writing."""


def _evaluator_config_hash(ds: Dataset, judge: JudgeRow | None) -> tuple[str, str]:
    from evalcore.assertions import ASSERTION_TYPES

    rubric = hash_obj(sorted((c.id, c.rubric) for c in ds.cases if c.rubric), 16)
    cfg = hash_obj(
        {
            "assertions": sorted(ASSERTION_TYPES),
            "judge": judge.identity if judge else None,
            "judge_params": judge.params if judge else None,
            "scoring": "layers-v2",
        },
        16,
    )
    return cfg, rubric


def build_manifest(
    run_id: str,
    run_type: str,
    resolved: ResolvedAgent,
    dv: DatasetVersion,
    ds: Dataset,
    samples: int,
    seed: int,
    judge: JudgeRow | None,
    concurrency: int = 1,
    run_budget_usd: float | None = None,
) -> RunManifest:
    from evalcore.manifest import evaluator_hash

    sha, dirty = git_info()
    cfg_hash, rubric_hash = _evaluator_config_hash(ds, judge)
    return RunManifest(
        run_id=run_id,
        run_type=run_type,
        agent=resolved.agent,
        agent_version=resolved.version,
        agent_hash=resolved.agent_hash,
        dataset_name=dv.dataset.name,
        dataset_path=dv.source_path,
        dataset_hash=dv.hash,
        fixture_hash=dv.fixture_hash,
        case_ids=[c.id for c in ds.cases],
        samples_per_case=samples,
        model_provider=resolved.provider,
        model=resolved.model,
        model_params={"temperature": 0, "seed": seed}
        if resolved.execution_kind == "synthetic"
        else {"harness_defaults": True},
        judge_backend=judge.backend if judge else "",
        judge_model=judge.model if judge else "",
        judge_prompt_hash=judge.prompt_hash if judge else "",
        tool_schema_hash=resolved.tool_schema_hash,
        git_commit=sha,
        git_dirty=dirty,
        concurrency=concurrency,
        seed=seed,
        execution_kind=resolved.execution_kind,
        model_resolved=resolved.model
        if resolved.execution_kind == "synthetic"
        else "",  # live: filled from provider-reported data
        evaluator_hash=evaluator_hash(),
        evaluator_config_hash=cfg_hash,
        rubric_hash=rubric_hash,
        agent_config={
            **resolved.config,
            "spec": resolved.spec,
            **({"run_budget_usd": run_budget_usd} if run_budget_usd else {}),
        },
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
    run_type: str | None = None,
    judge: JudgeRow | None = None,
    queue: bool = True,
    concurrency: int = 1,
    run_budget_usd: float | None = None,
) -> Run:
    existing = s.get(Run, run_id)
    if existing is not None:
        return existing
    from .catalog import sync_agent_version

    resolved = resolve(agent_spec)
    kind = "live" if resolved.execution_kind == "live" else "synthetic_demo"
    if run_type and run_type != kind and run_type != "ci_gate":
        raise ValueError(
            f"run_type '{run_type}' contradicts the resolved agent ({resolved.execution_kind}); it is derived, not chosen"
        )
    av = sync_agent_version(s, agent_spec)
    ds = load_dataset_from_db(s, dv)
    man = build_manifest(run_id, run_type or kind, resolved, dv, ds, samples, seed, judge, concurrency, run_budget_usd)
    run = Run(
        id=run_id,
        name=name,
        run_type=run_type or kind,
        status="queued",
        agent_version_id=av.id,
        dataset_version_id=dv.id,
        judge_config_id=judge.id if judge else None,
        samples_per_case=samples,
        seed=seed,
        manifest=man.to_dict(),
        manifest_hash=man.content_hash(),
        progress_total=len(ds.cases) * samples,
        is_synthetic=resolved.execution_kind == "synthetic",
    )
    s.add(run)
    s.flush()
    if queue:
        s.add(RunExecution(run_id=run.id, status="queued"))
    s.flush()
    return run


_REDACTOR = Redactor(max_text=20_000)


MAX_STR_CHARS = 20_000  # any single stored string; agent/tool output is untrusted and may be enormous
MAX_SPANS_PER_SAMPLE = 500


def _cap(obj: Any) -> Any:
    """Bound the size of free-form stored values (structure, numbers and booleans are preserved)."""
    if isinstance(obj, str):
        return (
            obj
            if len(obj) <= MAX_STR_CHARS
            else obj[:MAX_STR_CHARS] + f"...[truncated {len(obj) - MAX_STR_CHARS} chars]"
        )
    if isinstance(obj, dict):
        return {k: _cap(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_cap(v) for v in obj[:2000]]
    return obj


def _persist(s: Session, run: Run, smp: SampleResult, input_text: str) -> Sample:
    """Persist one sample. Everything free-form is redacted BEFORE it reaches the database."""
    rd = _REDACTOR
    res = smp.result
    trace_id = res.spans[0].trace_id if res.spans else ""
    row = Sample(
        run_id=run.id,
        case_id=smp.case_id,
        category=smp.category,
        sample_index=smp.sample_index,
        status=smp.status.value,
        error_kind=res.error_kind,
        input_text=_cap(rd.text(input_text)),
        final_output=_cap(rd.text(res.final_output)),
        tool_sequence=rd.apply(res.tool_names),
        latency_ms=res.latency_ms,
        input_tokens=res.input_tokens,
        output_tokens=res.output_tokens,
        cost_usd=res.cost_usd,
        turns=res.turns,
        steps=res.steps,
        result=_cap(rd.apply(json.loads(res.model_dump_json(exclude={"spans"})))),
        judge=rd.apply(smp.judge) if smp.judge else None,
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
                expected=rd.apply(a.expected),
                actual=rd.apply(a.actual),
                evidence=rd.text(a.evidence),
                label=a.label,
            )
        )
    for sp in res.spans[:MAX_SPANS_PER_SAMPLE]:
        s.add(
            SpanRow(
                sample_id=row.id,
                trace_id=sp.trace_id,
                span_id=sp.span_id,
                parent_id=sp.parent_id,
                name=rd.text(sp.name),
                kind=sp.kind,
                start_ms=sp.start_ms,
                duration_ms=sp.duration_ms,
                status=sp.status,
                attributes=_cap(rd.apply(sp.attributes)),
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
    commit_every: int = 5,
    owner_check: Callable[[], bool] | None = None,
    concurrency: int | None = None,
) -> None:
    """Execute every missing (case, sample_index). Idempotent and resume-safe.

    * ``owner_check`` is the FENCE: called before every write batch; if the worker lost its lease it raises
      :class:`LeaseLost` and nothing further is committed.
    * An optional per-run budget (``manifest.agent_config.run_budget_usd``, API-equivalent estimate) stops a live run early;
      the run is then marked failed/incomplete (never silently "succeeded").
    """
    dv = run.dataset_version
    ds = load_dataset_from_db(s, dv)
    cfg = run.manifest.get("agent_config", {})
    resolved = resolve(cfg.get("spec") or f"{run.agent_version.agent.name}:{run.agent_version.version}")
    judge = judge_admitted = None
    if run.judge is not None:
        judge, judge_admitted = judges.build_judge(run.judge), judges.judge_admitted(s, run.judge_config_id)
        run.judge_admitted = bool(judge_admitted)
    done = {(c, i) for c, i in s.execute(select(Sample.case_id, Sample.sample_index).where(Sample.run_id == run.id))}
    run.status = "running"
    run.progress_total = len(ds.cases) * run.samples_per_case
    pending = [(c, i) for c in ds.cases for i in range(run.samples_per_case) if (c.id, i) not in done]
    n, spent, budget = len(done), 0.0, cfg.get("run_budget_usd")
    workers = max(1, concurrency or int(run.manifest.get("concurrency", 1)))

    def one(job: tuple[Case, int]) -> tuple[Case, SampleResult]:
        case, i = job
        return case, execute_sample(
            resolved.adapter, case, run.id, i, run.seed, resolved.price_table, judge, bool(judge_admitted)
        )

    def handle(case: Case, smp: SampleResult) -> bool:
        nonlocal n, spent
        if owner_check is not None and not owner_check():
            raise LeaseLost(f"lost the lease on run {run.id}")
        _persist(s, run, smp, case.input)
        n += 1
        run.progress_done = n
        spent += float(smp.result.metadata.get("api_equivalent_cost_usd") or smp.result.cost_usd or 0.0)
        if n % commit_every == 0:
            s.commit()
            if heartbeat:
                heartbeat()
            if on_progress:
                on_progress(n, run.progress_total)
        return not (budget and spent > float(budget))

    stopped = False
    if workers == 1:
        for job in pending:
            case, smp = one(job)
            if not handle(case, smp):
                stopped = True
                break
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(one, j) for j in pending]
            try:
                for f in as_completed(futs):
                    case, smp = f.result()
                    if not handle(case, smp):
                        stopped = True
                        break
            finally:
                if stopped or any(not f.done() for f in futs):
                    for g in futs:  # LeaseLost / any error / budget stop: do not keep spending on queued samples
                        g.cancel()
    s.flush()
    finalize_run(s, run)
    if stopped:
        run.status, run.error = (
            "failed",
            f"run budget exceeded (~${spent:.2f} of ${float(budget):.2f} API-equivalent); evidence is incomplete",
        )


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
    run.summary = _json_safe(summarize(samples, run.samples_per_case, run.manifest.get("case_ids")))
    observed = sorted({x.result.model for x in samples if x.result.model and x.status != SampleStatus.EXECUTION_ERROR})
    if run.manifest.get("execution_kind") == "live" and observed:
        man = dict(run.manifest)
        man["model_resolved"] = (
            observed[0] if len(observed) == 1 else "mixed:" + "+".join(observed)
        )  # alias drift stays visible
        run.manifest = man
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
    r = resolve(run.manifest.get("agent_config", {}).get("spec") or agent_spec(run))
    return {
        "agent": r.agent,
        "version": r.version,
        "agent_hash": r.agent_hash,
        "stored_agent_hash": run.agent_version.agent_hash,
        "matches": r.agent_hash == run.agent_version.agent_hash,
    }


def hash_of(obj: Any) -> str:
    return hash_obj(obj, 12)
