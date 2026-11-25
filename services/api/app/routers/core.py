"""Meta, health, overview, agents, datasets, runs, samples, traces."""

from __future__ import annotations

from typing import Any

from evalcore.manifest import EVALUATOR_VERSION
from evalcore.semconv import SEMCONV_VERSION
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from .. import schemas as sc
from ..config import Settings, get_settings
from ..db import get_session
from ..models import (
    Agent,
    AgentVersion,
    Dataset,
    DatasetVersion,
    DistilledCandidate,
    EvalCase,
    Run,
    RunExecution,
    Sample,
    SpanRow,
)
from ..security import client_key, live_limiter, require_admin
from ..services import comparisons as cmp_svc
from ..services import queries
from ..services import runs as run_svc
from ..services.catalog import sync_dataset

router = APIRouter()
NOTICE = (
    "All results are SYNTHETIC FIXTURE EVIDENCE from scripted, seeded reference agents. "
    "They demonstrate the evaluation "
    "machinery and are not benchmarks of any real model or production system."
)


@router.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["ops"])
def ready(s: Session = Depends(get_session)) -> dict[str, Any]:
    s.execute(text("SELECT 1"))
    n = s.scalar(select(func.count(Run.id))) or 0
    return {"status": "ready", "database": "ok", "runs": n}


@router.get("/api/meta", response_model=sc.Meta, tags=["meta"])
def meta(settings: Settings = Depends(get_settings)) -> sc.Meta:
    return sc.Meta(
        name="Agent Reliability Studio",
        version="0.1.0",
        demo_mode=settings.demo_mode,
        environment=settings.environment,
        synthetic_notice=NOTICE,
        semconv=SEMCONV_VERSION,
        evaluator_version=EVALUATOR_VERSION,
    )


# --------------------------------------------------------------------------- agents / datasets
@router.get("/api/agents", response_model=list[sc.AgentVersionOut], tags=["agents"])
def agents(s: Session = Depends(get_session)) -> list[sc.AgentVersionOut]:
    rows = s.scalars(
        select(AgentVersion)
        .options(joinedload(AgentVersion.agent))
        .order_by(AgentVersion.agent_id, AgentVersion.version)
    ).all()
    return [
        sc.AgentVersionOut(
            id=r.id,
            agent=r.agent.name,
            version=r.version,
            role=r.role,
            agent_hash=r.agent_hash,
            prompt_hash=r.prompt_hash,
            tool_schema_hash=r.tool_schema_hash,
            model=r.model,
            git_commit=r.git_commit,
            frozen=r.frozen,
            notes=r.notes,
        )
        for r in rows
    ]


def _dv_out(s: Session, dv: DatasetVersion) -> sc.DatasetVersionOut:
    return sc.DatasetVersionOut(
        id=dv.id,
        dataset=dv.dataset.name,
        kind=dv.dataset.kind,
        version=dv.version,
        hash=dv.hash,
        fixture_version=dv.fixture_version,
        fixture_hash=dv.fixture_hash,
        published=dv.published,
        case_count=dv.case_count,
        source_path=dv.source_path,
        description=dv.description,
        categories=queries.dataset_categories(s, dv.id),
    )


@router.get("/api/datasets", response_model=list[sc.DatasetVersionOut], tags=["datasets"])
def datasets(s: Session = Depends(get_session)) -> list[sc.DatasetVersionOut]:
    rows = s.scalars(
        select(DatasetVersion)
        .options(joinedload(DatasetVersion.dataset))
        .order_by(DatasetVersion.dataset_id, DatasetVersion.version)
    ).all()
    return [_dv_out(s, r) for r in rows]


@router.get("/api/datasets/{name}/{version}", response_model=sc.DatasetDetail, tags=["datasets"])
def dataset_detail(name: str, version: str, s: Session = Depends(get_session)) -> sc.DatasetDetail:
    dv = s.scalar(
        select(DatasetVersion)
        .join(Dataset)
        .options(joinedload(DatasetVersion.dataset))
        .where(Dataset.name == name, DatasetVersion.version == version)
    )
    if dv is None:
        raise HTTPException(404, "dataset version not found")
    cases = s.scalars(select(EvalCase).where(EvalCase.dataset_version_id == dv.id).order_by(EvalCase.id)).all()
    return sc.DatasetDetail(
        **_dv_out(s, dv).model_dump(),
        cases=[
            sc.CaseOut(
                case_id=c.case_id,
                title=c.title,
                category=c.category,
                severity=c.severity,
                description=c.description,
                tags=list(c.tags),
                definition=c.definition,
            )
            for c in cases
        ],
    )


@router.get("/api/candidates", tags=["datasets"])
def distilled(s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = s.scalars(select(DistilledCandidate).order_by(DistilledCandidate.id.desc())).all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "source_sample_id": r.source_sample_id,
            "case": r.case,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- runs
@router.get("/api/runs", response_model=sc.RunList, tags=["runs"])
def list_runs(
    agent: str | None = None,
    version: str | None = None,
    model: str | None = None,
    dataset: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(25, ge=1, le=100),
    s: Session = Depends(get_session),
) -> sc.RunList:
    q = (
        select(Run)
        .join(AgentVersion, Run.agent_version_id == AgentVersion.id)
        .join(Agent, AgentVersion.agent_id == Agent.id)
        .join(DatasetVersion, Run.dataset_version_id == DatasetVersion.id)
        .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
    )
    if agent:
        q = q.where(Agent.name == agent)
    if version:
        q = q.where(AgentVersion.version == version)
    if model:
        q = q.where(AgentVersion.model == model)
    if dataset:
        q = q.where(Dataset.name == dataset)
    if status:
        q = q.where(Run.status == status)
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = (
        s.scalars(
            q.options(*queries.run_options())
            .order_by(Run.created_at.desc(), Run.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )
    return sc.RunList(page=page, page_size=page_size, total=total, items=[queries.run_out(r) for r in rows])


def _get_run(s: Session, run_id: str) -> Run:
    r = s.scalar(select(Run).options(*queries.run_options()).where(Run.id == run_id))
    if r is None:
        raise HTTPException(404, "run not found")
    return r


@router.get("/api/runs/{run_id}", response_model=sc.RunDetail, tags=["runs"])
def run_detail(run_id: str, s: Session = Depends(get_session)) -> sc.RunDetail:
    r = _get_run(s, run_id)
    av = r.agent_version
    return sc.RunDetail(
        **queries.run_out(r).model_dump(),
        manifest=r.manifest,
        summary=r.summary,
        agent_hash=av.agent_hash,
        prompt_hash=av.prompt_hash,
        tool_schema_hash=av.tool_schema_hash,
        clusters=queries.clusters_for(s, run_id),
    )


@router.get("/api/runs/{run_id}/progress", tags=["runs"])
def run_progress(run_id: str, s: Session = Depends(get_session)) -> dict[str, Any]:
    r = _get_run(s, run_id)
    ex = s.scalar(select(RunExecution).where(RunExecution.run_id == run_id).order_by(RunExecution.id.desc()).limit(1))
    return {
        "status": r.status,
        "done": r.progress_done,
        "total": r.progress_total,
        "error": r.error,
        "attempt": ex.attempt if ex else 0,
        "execution_status": ex.status if ex else None,
    }


@router.get("/api/runs/{run_id}/samples", response_model=sc.SampleList, tags=["runs"])
def run_samples(
    run_id: str,
    case: str | None = None,
    status: str | None = None,
    category: str | None = None,
    label: str | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, ge=1, le=200),
    s: Session = Depends(get_session),
) -> sc.SampleList:
    from ..models import FailureLabel

    q = select(Sample).where(Sample.run_id == run_id)
    if case:
        q = q.where(Sample.case_id == case)
    if status:
        q = q.where(Sample.status == status)
    if category:
        q = q.where(Sample.category == category)
    if label:
        q = q.where(
            Sample.id.in_(
                select(FailureLabel.sample_id).where(FailureLabel.run_id == run_id, FailureLabel.label == label)
            )
        )
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = s.scalars(
        q.order_by(Sample.case_id, Sample.sample_index).offset((page - 1) * page_size).limit(page_size)
    ).all()
    labs = queries.labels_by_sample(s, [r.id for r in rows])
    return sc.SampleList(
        page=page, page_size=page_size, total=total, items=[queries.sample_out(r, labs.get(r.id, [])) for r in rows]
    )


@router.get("/api/samples/{sample_id}", response_model=sc.SampleDetail, tags=["runs"])
def sample(sample_id: int, s: Session = Depends(get_session)) -> sc.SampleDetail:
    smp = s.get(Sample, sample_id)
    if smp is None:
        raise HTTPException(404, "sample not found")
    return queries.sample_detail(s, smp)


@router.get("/api/samples/{sample_id}/trace", response_model=sc.TraceOut, tags=["traces"])
def trace(sample_id: int, s: Session = Depends(get_session)) -> sc.TraceOut:
    smp = s.get(Sample, sample_id)
    if smp is None:
        raise HTTPException(404, "sample not found")
    spans = s.scalars(
        select(SpanRow).where(SpanRow.sample_id == sample_id).order_by(SpanRow.start_ms, SpanRow.id)
    ).all()
    total = max((sp.start_ms + sp.duration_ms for sp in spans), default=0.0)
    return sc.TraceOut(
        sample_id=sample_id,
        trace_id=smp.trace_id,
        case_id=smp.case_id,
        run_id=smp.run_id,
        trajectory=list(smp.tool_sequence or []),
        total_ms=total,
        spans=[sc.SpanOut.model_validate(sp) for sp in spans],
    )


@router.get("/api/traces", tags=["traces"])
def traces(
    run_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(30, ge=1, le=100),
    s: Session = Depends(get_session),
) -> dict[str, Any]:
    q = select(Sample)
    if run_id:
        q = q.where(Sample.run_id == run_id)
    if status:
        q = q.where(Sample.status == status)
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = s.scalars(q.order_by(Sample.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    labs = queries.labels_by_sample(s, [r.id for r in rows])
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [queries.sample_out(r, labs.get(r.id, [])).model_dump() for r in rows],
    }


# --------------------------------------------------------------------------- mutations (admin/local only)
@router.post("/api/runs", response_model=sc.RunOut, tags=["runs"], dependencies=[Depends(require_admin)])
def create_run(
    body: sc.RunCreate, request: Request, s: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> sc.RunOut:
    live_limiter.check(client_key(request))
    agent, _, _ver = body.agent.partition(":")
    if agent == "coding" and not settings.enable_coding_execution:
        raise HTTPException(403, "coding-agent execution is local/admin only (set ENABLE_CODING_EXECUTION=true)")
    name, _, dver = body.dataset.partition(":")
    dv = s.scalar(
        select(DatasetVersion)
        .join(Dataset)
        .options(joinedload(DatasetVersion.dataset))
        .where(Dataset.name == name, DatasetVersion.version == dver)
    )
    if dv is None:
        raise HTTPException(404, "dataset version not found (sync it first)")
    rid = f"run-{run_svc.hash_of([body.agent, body.dataset, body.samples, body.seed, str(func.now())])}"
    try:
        run = run_svc.create_run(
            s,
            run_id=rid,
            name=body.name or f"{body.agent} on {body.dataset}",
            agent_spec=body.agent,
            dv=dv,
            samples=max(1, min(body.samples, 10)),
            seed=body.seed,
        )  # run_type / provenance are DERIVED from the resolved agent, never chosen by the caller
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    s.commit()
    return queries.run_out(_get_run(s, run.id))


@router.post(
    "/api/comparisons", response_model=sc.ComparisonOut, tags=["comparisons"], dependencies=[Depends(require_admin)]
)
def create_comparison(body: sc.CompareCreate, s: Session = Depends(get_session)) -> sc.ComparisonOut:
    if body.policy not in cmp_svc.POLICIES or body.mode not in ("strict", "exploratory"):
        raise HTTPException(422, "unknown policy or mode")
    try:
        comp = cmp_svc.create_comparison(
            s, body.baseline_run_id, body.candidate_run_id, mode=body.mode, policy_name=body.policy
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    gate = cmp_svc.create_gate(s, comp)
    s.commit()
    return queries.comparison_out(comp, gate)


_ = sync_dataset
