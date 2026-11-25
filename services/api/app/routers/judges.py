"""Judges, calibration and human annotation (blind presentation, agreement, adjudication)."""

from __future__ import annotations

import re
from typing import Any

from evalcore.calibration import AdmissionPolicy
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas as sc
from ..config import get_settings
from ..db import get_session
from ..models import CalibrationItem, CalibrationRun, CalibrationSet, HumanAnnotation, JudgeConfig
from ..security import annotation_limiter, client_key, require_admin
from ..services import judges as judge_svc

router = APIRouter(prefix="/api", tags=["judges"])
ANNOTATOR = re.compile(
    r"[A-Za-z0-9_.-]{2,40}"
)  # always used with fullmatch (a bare `$` would accept a trailing newline)
MAX_HUMAN_ROWS = 5000


def _run_dict(c: CalibrationRun) -> dict[str, Any]:
    return {
        "id": c.id,
        "n_items_used": c.n_items_used,
        "admitted": c.admitted,
        "reasons": c.reasons,
        "metrics": c.metrics,
        "policy": c.policy,
        "reference_sources": c.reference_sources,
        "created_at": c.created_at.isoformat(),
        "set_id": c.set_id,
    }


def _judge_out(s: Session, j: JudgeConfig) -> sc.JudgeOut:
    hist = list(
        s.scalars(select(CalibrationRun).where(CalibrationRun.judge_config_id == j.id).order_by(CalibrationRun.id))
    )
    latest = hist[-1] if hist else None
    admitted = bool(latest and latest.admitted)
    label = (
        "CALIBRATED — allowed for gating"
        if admitted
        else "NOT CALIBRATED — diagnostic only" + ("" if latest else " (never calibrated)")
    )
    return sc.JudgeOut(
        id=j.id,
        name=j.name,
        backend=j.backend,
        model=j.model,
        prompt_hash=j.prompt_hash,
        identity=j.identity,
        dimension=j.dimension,
        rubric_version=j.rubric_version,
        status="calibrated" if admitted else "not_calibrated",
        status_label=label,
        admitted=admitted,
        latest=_run_dict(latest) if latest else None,
        history=[_run_dict(h) for h in reversed(hist)],
    )


@router.get("/judges", response_model=list[sc.JudgeOut])
def judges(limit: int = Query(200, ge=1, le=500), s: Session = Depends(get_session)) -> list[sc.JudgeOut]:
    return [_judge_out(s, j) for j in s.scalars(select(JudgeConfig).order_by(JudgeConfig.id).limit(limit))]


@router.get("/judges/{jid}", response_model=sc.JudgeOut)
def judge(jid: int, s: Session = Depends(get_session)) -> sc.JudgeOut:
    j = s.get(JudgeConfig, jid)
    if j is None:
        raise HTTPException(404, "judge not found")
    return _judge_out(s, j)


@router.get("/calibration/{run_id}/items")
def calibration_items(run_id: int, s: Session = Depends(get_session)) -> dict[str, Any]:
    """Per-item predictions vs reference labels (after the fact; the annotation UI never sees these)."""
    c = s.get(CalibrationRun, run_id)
    if c is None:
        raise HTTPException(404, "calibration run not found")
    items = s.scalars(
        select(CalibrationItem).where(CalibrationItem.set_id == c.set_id).order_by(CalibrationItem.item_id)
    ).all()
    rows = [
        {
            "item_id": i.item_id,
            "input": i.input,
            "candidate_output": i.candidate_output,
            "reference_label": i.reference_label,
            "label_source": i.label_source,
            "predicted": c.predictions.get(i.item_id),
            "notes": i.notes,
        }
        for i in items
        if i.item_id in c.predictions
    ]
    return {"run": _run_dict(c), "items": rows, "errors": [r for r in rows if r["predicted"] != r["reference_label"]]}


@router.post("/judges/{jid}/calibrate", response_model=sc.JudgeOut, dependencies=[Depends(require_admin)])
def calibrate(jid: int, set_name: str = "calibration", s: Session = Depends(get_session)) -> sc.JudgeOut:
    j = s.get(JudgeConfig, jid)
    cset = s.scalar(select(CalibrationSet).where(CalibrationSet.name == set_name).order_by(CalibrationSet.id.desc()))
    if j is None or cset is None:
        raise HTTPException(404, "judge or calibration set not found")
    st = get_settings()
    if cset.n_items > st.calibrate_max_items:
        raise HTTPException(
            413, f"calibration set too large for a synchronous request (max {st.calibrate_max_items} items)"
        )
    try:
        judge_svc.calibrate(s, j, cset, AdmissionPolicy(), deadline_s=st.calibrate_max_seconds)
    except TimeoutError:
        s.rollback()
        raise HTTPException(
            504, f"calibration exceeded {st.calibrate_max_seconds:.0f}s; nothing was recorded"
        ) from None
    s.commit()
    return _judge_out(s, j)


# --------------------------------------------------------------------- annotation
def _cset(s: Session, name: str) -> CalibrationSet:
    c = s.scalar(select(CalibrationSet).where(CalibrationSet.name == name).order_by(CalibrationSet.id.desc()))
    if c is None:
        raise HTTPException(404, "calibration set not found")
    return c


@router.get("/annotation/next", response_model=sc.BlindItem | None)
def next_item(
    annotator: str = Query(..., pattern=r"^[A-Za-z0-9_.-]{2,40}$"),
    set_name: str = "calibration",
    s: Session = Depends(get_session),
) -> sc.BlindItem | None:
    """Blind: returns input/candidate/rubric only. No reference label, no judge verdict, no other annotator's label."""
    cs = _cset(s, set_name)
    done = select(HumanAnnotation.item_pk).where(HumanAnnotation.annotator == annotator)
    it = s.scalar(
        select(CalibrationItem)
        .where(CalibrationItem.set_id == cs.id, CalibrationItem.id.not_in(done))
        .order_by(CalibrationItem.item_id)
        .limit(1)
    )
    if it is None:
        return None
    return sc.BlindItem(item_id=it.item_id, input=it.input, candidate_output=it.candidate_output, rubric=it.rubric)


@router.get("/annotation/progress")
def progress(
    annotator: str = Query(..., pattern=r"^[A-Za-z0-9_.-]{2,40}$"),
    set_name: str = "calibration",
    s: Session = Depends(get_session),
) -> dict[str, Any]:
    cs = _cset(s, set_name)
    total = cs.n_items
    rows = s.execute(
        select(HumanAnnotation.label)
        .join(CalibrationItem, HumanAnnotation.item_pk == CalibrationItem.id)
        .where(CalibrationItem.set_id == cs.id, HumanAnnotation.annotator == annotator)
    ).all()
    return {
        "annotator": annotator,
        "total": total,
        "labelled": sum(1 for (x,) in rows if x is not None),
        "skipped": sum(1 for (x,) in rows if x is None),
    }


@router.post("/annotation", tags=["judges"])
def annotate(body: sc.AnnotationIn, request: Request, s: Session = Depends(get_session)) -> dict[str, Any]:
    """PUBLIC, UNTRUSTED annotation. Handles are unauthenticated, so rows are stored as ``public_untrusted``: they are shown with
    that label, never counted as human calibration evidence and never able to change a reference label or a gate. The trusted,
    authenticated human workflow is ``POST /annotation/trusted`` (admin only)."""
    annotation_limiter.check(client_key(request))
    return _store_annotation(body, s, source="public_untrusted")


@router.post("/annotation/trusted", tags=["judges"], dependencies=[Depends(require_admin)])
def annotate_trusted(body: sc.AnnotationIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    """AUTHENTICATED human annotation (admin token): the only path that creates ``source="human"`` rows."""
    return _store_annotation(body, s, source="human")


def _public_rows(s: Session) -> int:
    return s.scalar(select(func.count(HumanAnnotation.id)).where(HumanAnnotation.source == "public_untrusted")) or 0


def _store_annotation(body: sc.AnnotationIn, s: Session, source: str) -> dict[str, Any]:
    if not ANNOTATOR.fullmatch(body.annotator) or body.annotator.startswith("demo-annotator"):
        raise HTTPException(422, "annotator must be 2-40 chars [A-Za-z0-9_.-] and not a reserved demo id")
    if source == "public_untrusted" and _public_rows(s) >= MAX_HUMAN_ROWS:
        raise HTTPException(429, "annotation capacity reached for this deployment")
    cs = _cset(s, body.set_name)
    it = s.scalar(
        select(CalibrationItem).where(CalibrationItem.set_id == cs.id, CalibrationItem.item_id == body.item_id)
    )
    if it is None:
        raise HTTPException(404, "item not found")
    row = s.scalar(
        select(HumanAnnotation).where(HumanAnnotation.item_pk == it.id, HumanAnnotation.annotator == body.annotator)
    )
    if row is None:
        s.add(
            HumanAnnotation(
                item_pk=it.id, annotator=body.annotator, label=body.label, note=body.note[:500], source=source
            )
        )
    elif row.label is None and body.label is not None:
        row.label, row.note = body.label, body.note[:500]  # a skipped item may be filled in later
    else:
        # Append-only: annotator ids are self-declared handles (no auth), so an existing label is never overwritten.
        raise HTTPException(409, "this annotator has already labelled this item; labels are append-only")
    s.commit()
    return {"ok": True}


@router.get("/annotation/summary")
def summary(set_name: str = "calibration", s: Session = Depends(get_session)) -> dict[str, Any]:
    cs = _cset(s, set_name)
    info = judge_svc.annotation_summary(s, cs.id)
    items = {i.item_id: i for i in s.scalars(select(CalibrationItem).where(CalibrationItem.set_id == cs.id))}
    queue = [
        {
            "item_id": k,
            "labels": v,
            "input": items[k].input,
            "candidate_output": items[k].candidate_output,
            "rubric": items[k].rubric,
        }
        for k, v in info["disagreements"].items()
    ]  # type: ignore[union-attr]
    adjud = {a.item_pk for a in s.scalars(select(HumanAnnotation).where(HumanAnnotation.adjudicated.is_(True)))}
    pk_by_item = {k: v.id for k, v in items.items()}
    for q in queue:
        q["adjudicated"] = pk_by_item[q["item_id"]] in adjud
    src = info["annotator_sources"]  # type: ignore[index]
    # Anonymous public handles are UNTRUSTED: they never count toward a consensus claim.
    n_ann = sum(1 for a in info["annotators"] if src.get(a) != "public_untrusted")  # type: ignore[attr-defined,union-attr]
    return {
        "annotators": info["annotators"],
        "n_labels": info["n_labels"],
        "kappa": info["kappa"],
        "items_compared": info["items_compared"],
        "sources": info["sources"],
        "disagreement_queue": queue,
        "annotator_sources": src,
        "untrusted_annotators": sorted(a for a, v in src.items() if v == "public_untrusted"),  # type: ignore[attr-defined]
        "consensus_claimed": n_ann >= 2,
        "note": (
            "Agreement requires >= 2 annotators on shared items; with fewer, no consensus is claimed. "
            "Rows with source 'synthetic_demo' are seeded stand-ins, not human labels; 'public_untrusted' rows come from "
            "anonymous, unauthenticated handles and never count as evidence."
        ),
    }


@router.post("/annotation/adjudicate")
def adjudicate(body: sc.AdjudicationIn, request: Request, s: Session = Depends(get_session)) -> dict[str, Any]:
    """PUBLIC, UNTRUSTED adjudication: stored as ``public_untrusted`` and NOT flagged adjudicated (an anonymous handle cannot
    adjudicate). Never changes a reference label or a gate. Authenticated adjudication: ``POST /annotation/trusted/adjudicate``."""
    annotation_limiter.check(client_key(request))
    return _store_adjudication(body, s, source="public_untrusted")


@router.post("/annotation/trusted/adjudicate", dependencies=[Depends(require_admin)])
def adjudicate_trusted(body: sc.AdjudicationIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    """AUTHENTICATED adjudication (admin token): the only path that creates ``adjudicated=True`` rows."""
    return _store_adjudication(body, s, source="human")


def _store_adjudication(body: sc.AdjudicationIn, s: Session, source: str) -> dict[str, Any]:
    if not ANNOTATOR.fullmatch(body.adjudicator) or body.adjudicator.startswith("demo-annotator"):
        raise HTTPException(422, "adjudicator must be 2-40 chars [A-Za-z0-9_.-] and not a reserved demo id")
    if source == "public_untrusted" and _public_rows(s) >= MAX_HUMAN_ROWS:
        raise HTTPException(429, "annotation capacity reached for this deployment")
    cs = _cset(s, body.set_name)
    it = s.scalar(
        select(CalibrationItem).where(CalibrationItem.set_id == cs.id, CalibrationItem.item_id == body.item_id)
    )
    if it is None:
        raise HTTPException(404, "item not found")
    who = f"adjudicator:{body.adjudicator}"
    if s.scalar(select(HumanAnnotation.id).where(HumanAnnotation.item_pk == it.id, HumanAnnotation.annotator == who)):
        raise HTTPException(409, "this adjudicator has already ruled on this item")
    s.add(
        HumanAnnotation(
            item_pk=it.id,
            annotator=who,
            label=body.label,
            note=body.note[:500],
            source=source,
            adjudicated=(source == "human"),
        )
    )
    s.commit()
    return {"ok": True}
