"""Judge construction, calibration runs and admission lookups."""

from __future__ import annotations

import time
from typing import Any

from evalcore.calibration import AdmissionPolicy, admit, calibration_metrics
from evalcore.judge import HeuristicJudge, Judge, JudgeConfig, LiteLLMBackend
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CalibrationItem, CalibrationRun, CalibrationSet, HumanAnnotation
from ..models import JudgeConfig as JudgeRow


def build_judge(row: JudgeRow) -> Judge:
    cfg = JudgeConfig(backend=row.backend, model=row.model, dimension=row.dimension, rubric_version=row.rubric_version)
    if row.backend == "heuristic":
        be = HeuristicJudge(
            model=row.model,
            strictness=float(row.params.get("strictness", 0.6)),
            check_forbidden=bool(row.params.get("check_forbidden", True)),
        )
    elif row.backend == "litellm":
        be = LiteLLMBackend(row.model)
    else:
        raise ValueError(f"unknown judge backend {row.backend}")
    return Judge(be, cfg)


def calibrate(
    s: Session,
    judge_row: JudgeRow,
    cset: CalibrationSet,
    policy: AdmissionPolicy | None = None,
    limit: int | None = None,
    deadline_s: float | None = None,
) -> CalibrationRun:
    """Run a judge over a calibration set and record metrics + admission. Never trusts an uncalibrated judge."""
    policy = policy or AdmissionPolicy()
    items = list(
        s.scalars(select(CalibrationItem).where(CalibrationItem.set_id == cset.id).order_by(CalibrationItem.item_id))
    )
    if limit:
        items = items[:limit]
    judge = build_judge(judge_row)
    preds: dict[str, bool] = {}
    failures = 0
    t_end = time.monotonic() + deadline_s if deadline_s else None
    for it in items:
        if t_end is not None and time.monotonic() > t_end:
            raise TimeoutError(f"calibration exceeded its {deadline_s:.0f}s deadline")
        rubric = "\n".join(
            [f"MUST: {m}" for m in it.rubric.get("must", [])]
            + [f"MUST_NOT: {m}" for m in it.rubric.get("must_not", [])]
        )
        out = judge.evaluate(rubric, it.input, it.candidate_output)
        if out.verdict is None:
            failures += (
                1  # a judge that cannot produce valid output counts as a wrong prediction for the label it missed
            )
            preds[it.item_id] = not it.reference_label
        else:
            preds[it.item_id] = out.verdict.passed
    m = calibration_metrics([preds[i.item_id] for i in items], [i.reference_label for i in items])
    dec = admit(m, policy)
    reasons = list(dec.reasons) + ([f"{failures} malformed/failed judge outputs counted as wrong"] if failures else [])
    sources: dict[str, int] = {}
    for it in items:
        sources[it.label_source] = sources.get(it.label_source, 0) + 1
    row = CalibrationRun(
        judge_config_id=judge_row.id,
        set_id=cset.id,
        n_items_used=len(items),
        policy=policy.to_dict(),
        metrics=m.to_dict(),
        predictions=preds,
        admitted=dec.admitted and failures == 0,
        reasons=reasons,
        reference_sources=sources,
    )
    s.add(row)
    s.flush()
    return row


def latest_calibration(s: Session, judge_id: int) -> CalibrationRun | None:
    return s.scalar(
        select(CalibrationRun)
        .where(CalibrationRun.judge_config_id == judge_id)
        .order_by(CalibrationRun.id.desc())
        .limit(1)
    )


def judge_admitted(s: Session, judge_id: int | None) -> bool:
    """A judge may gate only if its EXACT identity (backend, model, prompt hash) has an admitted latest calibration."""
    if judge_id is None:
        return True  # no judge involved
    c = latest_calibration(s, judge_id)
    return bool(c and c.admitted)


def annotation_summary(s: Session, set_id: int) -> dict[str, Any]:
    from evalcore.calibration import find_disagreements, mean_pairwise_kappa

    rows = s.execute(
        select(HumanAnnotation, CalibrationItem)
        .join(CalibrationItem, HumanAnnotation.item_pk == CalibrationItem.id)
        .where(CalibrationItem.set_id == set_id, HumanAnnotation.label.is_not(None))
    ).all()
    by_annot: dict[str, dict[str, bool]] = {}
    sources: set[str] = set()
    annot_source: dict[str, str] = {}
    untrusted: dict[str, int] = {}
    for a, it in rows:
        sources.add(a.source)
        annot_source[a.annotator] = a.source
        if a.source == "public_untrusted":
            untrusted[a.annotator] = untrusted.get(a.annotator, 0) + 1  # reported separately, NEVER used as evidence
            continue
        by_annot.setdefault(a.annotator, {})[it.item_id] = bool(a.label)
    kappa, n = mean_pairwise_kappa(by_annot)
    return {
        "annotators": sorted(by_annot),
        "n_labels": len(rows),
        "kappa": kappa,
        "items_compared": n,
        "disagreements": find_disagreements(by_annot),
        "sources": sorted(sources),
        "annotator_sources": annot_source,
        "untrusted_label_counts": untrusted,
    }


def release_status(s: Session, judge_id: int):  # type: ignore[no-untyped-def]
    """Release eligibility of the judge's latest calibration (None if never calibrated)."""
    from evalcore.calibration import AdmissionPolicy, CalibrationMetrics, release_eligibility

    c = latest_calibration(s, judge_id)
    if c is None:
        return None
    m = CalibrationMetrics(**c.metrics)
    pol = AdmissionPolicy(**{k: v for k, v in c.policy.items() if k in AdmissionPolicy.__dataclass_fields__})
    return release_eligibility(c.admitted, m, c.reference_sources, pol)
