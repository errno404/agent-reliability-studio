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
    "demo-20": BootstrapPolicy(min_cases=20, alpha=0.05, n_boot=10_000, margin=0.05),
    "demo-15": BootstrapPolicy(min_cases=15, alpha=0.05, n_boot=10_000, margin=0.05),
    "demo-10": BootstrapPolicy(min_cases=10, alpha=0.05, n_boot=10_000, margin=0.05),
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


def create_comparison(
    s: Session,
    baseline_id: str,
    candidate_id: str,
    *,
    mode: str = "strict",
    policy_name: str = "production",
    name: str = "",
) -> Comparison:
    base, cand = s.get(Run, baseline_id), s.get(Run, candidate_id)
    if base is None or cand is None:
        raise LookupError("unknown run id")
    pol = POLICIES[policy_name]
    bs, cs = load_samples(s, baseline_id), load_samples(s, candidate_id)
    cmp = compare_runs(
        manifest_of(base),
        bs,
        manifest_of(cand),
        cs,
        pol,
        mode,
        base_complete=base.status == "succeeded",
        cand_complete=cand.status == "succeeded",
    )
    result: dict[str, Any] = {
        "bootstrap": asdict(cmp.bootstrap) if cmp.bootstrap else None,
        "mcnemar": asdict(cmp.mcnemar) if cmp.mcnemar else None,
        "baseline_summary": cmp.baseline_summary,
        "candidate_summary": cmp.candidate_summary,
        "category_deltas": cmp.category_deltas,
        "case_changes": cmp.case_changes,
        "new_failure_labels": cmp.new_failure_labels,
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
        policy=asdict(pol),
        decision=cmp.decision.value,
        valid=cmp.validity.valid,
        validity={
            "valid": cmp.validity.valid,
            "reasons": cmp.validity.reasons,
            "warnings": cmp.validity.warnings,
            "mode": cmp.validity.mode,
        },
        result=result,
        explanation=cmp.explanation,
    )
    s.add(row)
    s.flush()
    return row


def judge_ok_for(s: Session, *runs: Run) -> bool:
    return all(judges.judge_admitted(s, r.judge_config_id) for r in runs)


def create_gate(s: Session, comp: Comparison, conservative: bool = True) -> CiGateDecision:
    """Gate verdict. Refuses to gate on a judge whose exact configuration is not currently admitted."""
    from evalcore.compare import Comparison as EvalComparison
    from evalcore.manifest import ValidationReport
    from evalcore.stats import Decision

    base, cand = comp.baseline_run, comp.candidate_run
    ok = judge_ok_for(s, base, cand)
    shim = EvalComparison(
        validity=ValidationReport(comp.valid, [], comp.mode),
        decision=Decision(comp.decision),
        bootstrap=None,
        mcnemar=None,
        explanation=comp.explanation,
    )
    v = gate(shim, judge_ok=ok, conservative=conservative)
    if not comp.valid:
        v.reasons = [f"comparison is invalid: {'; '.join(comp.validity.get('reasons', []))}"] + [
            r for r in v.reasons if "invalid" not in r
        ]
    row = CiGateDecision(
        comparison_id=comp.id, verdict=v.verdict, reasons=v.reasons, judge_ok=ok, conservative=conservative
    )
    s.add(row)
    s.flush()
    return row


def latest_gate(s: Session) -> CiGateDecision | None:
    return s.scalar(select(CiGateDecision).order_by(CiGateDecision.id.desc()).limit(1))
