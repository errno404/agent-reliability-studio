"""`ars demo verify`: invariants the product story relies on. Failing here means the demo is broken."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import CalibrationRun, CiGateDecision, Comparison, Run, Sample, SpanRow


def verify_demo(s: Session) -> tuple[list[str], list[tuple[str, bool]]]:
    checks: list[tuple[str, bool]] = []

    def ck(name: str, ok: bool) -> None:
        checks.append((name, bool(ok)))

    runs = {r.id: r for r in s.scalars(select(Run))}
    ck("all demo runs succeeded", bool(runs) and all(r.status == "succeeded" for r in runs.values()))
    ck(
        "support v2 improves on v1 (synthetic)",
        runs["demo-support-v2"].summary["task_success"]["rate"]
        > runs["demo-support-v1"].summary["task_success"]["rate"],
    )
    comps = {c.name: c for c in s.scalars(select(Comparison))}
    decisions = {c.decision for c in comps.values()}
    ck(
        "comparison states cover improvement, inconclusive and invalid",
        {"significant_improvement", "inconclusive", "invalid"} <= decisions,
    )
    head = comps.get("Support v1 → v2")
    ck(
        "headline comparison names a localized 'address' regression",
        bool(head and "Localized regression: 'address'" in head.result.get("what_changed", "")),
    )
    ck(
        "an execution error exists and is not a quality failure",
        (s.scalar(select(func.count(Sample.id)).where(Sample.status == "execution_error")) or 0) > 0,
    )
    ck(
        "a prompt-injection failure exists",
        (
            s.scalar(
                select(func.count(Sample.id))
                .join(
                    __import__("app.models", fromlist=["FailureLabel"]).FailureLabel,
                    __import__("app.models", fromlist=["FailureLabel"]).FailureLabel.sample_id == Sample.id,
                )
                .where(
                    __import__("app.models", fromlist=["FailureLabel"]).FailureLabel.label == "prompt_injection_failure"
                )
            )
            or 0
        )
        > 0,
    )
    cals = list(s.scalars(select(CalibrationRun).order_by(CalibrationRun.id)))
    ck(
        "calibration history has an admitted and a failed judge",
        any(c.admitted for c in cals) and any(not c.admitted for c in cals),
    )
    ck("traces are persisted with spans", (s.scalar(select(func.count(SpanRow.id))) or 0) > 1000)
    gates = list(s.scalars(select(CiGateDecision)))
    ck("gate has both pass and fail verdicts", {g.verdict for g in gates} == {"pass", "fail"})
    ck("a gate was blocked by an uncalibrated judge", any(not g.judge_ok for g in gates))
    ck(
        "synthetic runs are labelled synthetic and live runs are labelled live (never blended)",
        all(
            (r.is_synthetic and r.run_type != "live" and r.manifest.get("execution_kind", "synthetic") == "synthetic")
            or (not r.is_synthetic and r.run_type == "live" and r.manifest.get("execution_kind") == "live")
            for r in runs.values()
        ),
    )
    problems = [n for n, ok in checks if not ok]
    return problems, checks
