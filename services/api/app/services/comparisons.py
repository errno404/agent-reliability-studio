"""Create comparisons + CI gate decisions and the plain-language 'what changed' summary."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from evalcore import BootstrapPolicy, RunManifest, compare_runs, gate
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CiGateDecision, Comparison, Run
from . import judges
from .runs import load_samples

POLICIES: dict[str, BootstrapPolicy] = {
    "production": BootstrapPolicy(min_cases=50, alpha=0.05, n_boot=10_000, margin=0.05),
    "demo-20": BootstrapPolicy(min_cases=20, alpha=0.05, n_boot=10_000, margin=0.05, max_missing_share=0.06),
    "demo-15": BootstrapPolicy(min_cases=15, alpha=0.05, n_boot=10_000, margin=0.05, max_missing_share=0.06),
    "demo-10": BootstrapPolicy(min_cases=10, alpha=0.05, n_boot=10_000, margin=0.05, max_missing_share=0.06),
}


def manifest_of(run: Run) -> RunManifest:
    return RunManifest(**run.manifest)


def what_changed(result: dict[str, Any], base_name: str, cand_name: str) -> str:
    """Only statements supported by the stored comparison evidence."""
    if not result:
        return "No comparison evidence."
    parts: list[str] = []
    boot = result.get("bootstrap") or {}
    if boot:
        d = boot["delta"] * 100
        parts.append(
            f"{cand_name} is {abs(d):.1f} points {'higher' if d >= 0 else 'lower'} than {base_name} on "
            f"{boot['n_common_cases']} matched cases ({boot['n_improved']} improved, {boot['n_regressed']} regressed)."
        )
    worst = [
        (c, v)
        for c, v in (result.get("category_deltas") or {}).items()
        if v.get("delta") is not None and v["delta"] < -0.0001
    ]
    if worst:
        c, v = min(worst, key=lambda kv: kv[1]["delta"])
        newl = result.get("new_failure_labels") or {}
        top = sorted(newl.items(), key=lambda x: -x[1])[:3]
        modes = ", ".join(f"{k} (+{n})" for k, n in top)
        extra = f" New/increased failure modes: {modes}." if newl else ""
        parts.append(
            f"Localized regression: '{c}' cases fell {abs(v['delta']) * 100:.0f} points "
            f"({v['baseline'] * 100:.0f}% → {v['candidate'] * 100:.0f}%).{extra}"
        )
    return " ".join(parts)


def _evaluate(s: Session, base: Run, cand: Run, mode: str, policy_name: str, intent: str):  # type: ignore[no-untyped-def]
    pol = POLICIES[policy_name]
    return compare_runs(
        manifest_of(base),
        load_samples(s, base.id),
        manifest_of(cand),
        load_samples(s, cand.id),
        pol,
        mode,
        base_complete=base.status == "succeeded",
        cand_complete=cand.status == "succeeded",
        intent=intent,
    )


def create_comparison(
    s: Session,
    baseline_id: str,
    candidate_id: str,
    *,
    mode: str = "strict",
    policy_name: str = "production",
    name: str = "",
    intent: str = "agent_change",
) -> Comparison:
    base, cand = s.get(Run, baseline_id), s.get(Run, candidate_id)
    if base is None or cand is None:
        raise LookupError("unknown run id")
    pol = POLICIES[policy_name]
    cmp = _evaluate(s, base, cand, mode, policy_name, intent)
    result: dict[str, Any] = {
        "bootstrap": asdict(cmp.bootstrap) if cmp.bootstrap else None,
        "mcnemar": asdict(cmp.mcnemar) if cmp.mcnemar else None,
        "mcnemar_note": "diagnostic only: per-case MAJORITY outcome over repeated samples, not the regression decision",
        "baseline_summary": cmp.baseline_summary,
        "candidate_summary": cmp.candidate_summary,
        "category_deltas": cmp.category_deltas,
        "case_changes": cmp.case_changes,
        "new_failure_labels": cmp.new_failure_labels,
        "intent": cmp.intent,
        "mode": cmp.mode,
        "end_to_end": cmp.end_to_end,
        "coverage": cmp.coverage,
        "incomplete_reasons": cmp.incomplete_reasons,
        "execution_kind": {"baseline": manifest_of(base).execution_kind, "candidate": manifest_of(cand).execution_kind},
        "authorization": (
            "release-grade evidence"
            if cmp.mode == "strict" and cmp.validity.valid
            else "INVALID: cannot authorise a release"
            if not cmp.validity.valid
            else "EXPLORATORY: cannot authorise a release"
        ),
    }
    if result["bootstrap"]:
        result["bootstrap"]["decision"] = str(cmp.bootstrap.decision.value) if cmp.bootstrap else None
        result["bootstrap"].pop("policy", None)
    result = json.loads(json.dumps(result, default=str))
    result["what_changed"] = what_changed(
        result,
        f"{base.agent_version.agent.name}:{base.agent_version.version}",
        f"{cand.agent_version.agent.name}:{cand.agent_version.version}",
    )
    row = Comparison(
        name=name or f"{base.name} → {cand.name}",
        baseline_run_id=baseline_id,
        candidate_run_id=candidate_id,
        mode=mode,
        policy_name=policy_name,
        policy={**asdict(pol), "intent": intent},
        decision=cmp.decision.value,
        valid=cmp.validity.valid,
        validity={
            "valid": cmp.validity.valid,
            "reasons": cmp.validity.reasons,
            "warnings": cmp.validity.warnings,
            "mode": cmp.validity.mode,
            "intent": intent,
        },
        result=result,
        explanation=cmp.explanation,
    )
    s.add(row)
    s.flush()
    row._eval = cmp  # type: ignore[attr-defined]  # transient: lets create_gate reuse the exact in-memory analysis
    return row


def judge_ok_for(s: Session, *runs: Run) -> bool:
    """RELEASE eligibility of every judge involved: admitted when the run executed AND its calibration is release-grade
    (trusted human/adjudicated labels + a confidence bound on false positives). Synthetic calibrations never qualify."""
    for r in runs:
        if r.judge_config_id is None:
            continue
        if not r.judge_admitted:
            return False
        st = judges.release_status(s, r.judge_config_id)
        if st is None or not st.eligible:
            return False
    return True


def create_gate(s: Session, comp: Comparison, release: bool = True) -> CiGateDecision:
    """Gate decision. ``release=True`` is the only mode that can authorise a release (strict, valid, complete, release-eligible judges)."""
    base, cand = comp.baseline_run, comp.candidate_run
    ev = getattr(comp, "_eval", None) or _evaluate(
        s, base, cand, comp.mode, comp.policy_name, comp.policy.get("intent", "agent_change")
    )
    ok = judge_ok_for(s, base, cand)
    v = gate(ev, judge_ok=ok, release=release)
    row = CiGateDecision(comparison_id=comp.id, verdict=v.verdict, reasons=v.reasons, judge_ok=ok, conservative=release)
    s.add(row)
    s.flush()
    return row


def latest_gate(s: Session) -> CiGateDecision | None:
    return s.scalar(select(CiGateDecision).order_by(CiGateDecision.id.desc()).limit(1))
