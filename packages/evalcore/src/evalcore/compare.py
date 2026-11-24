"""Baseline vs candidate comparison, with plain-language explanation and gate decision."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .manifest import RunManifest, ValidationReport, validate_pair
from .models import SampleResult
from .stats import (
    BootstrapPolicy,
    BootstrapResult,
    Decision,
    McNemarResult,
    case_pass_fraction,
    mcnemar_exact,
    paired_cluster_bootstrap,
)
from .summary import category_rates, summarize
from .trajectory import diff_trajectories


@dataclass
class Comparison:
    validity: ValidationReport
    decision: Decision
    bootstrap: BootstrapResult | None
    mcnemar: McNemarResult | None
    baseline_summary: dict[str, Any] = field(default_factory=dict)
    candidate_summary: dict[str, Any] = field(default_factory=dict)
    category_deltas: dict[str, dict[str, Any]] = field(default_factory=dict)
    case_changes: list[dict[str, Any]] = field(default_factory=list)
    new_failure_labels: dict[str, int] = field(default_factory=dict)
    explanation: str = ""


def explain(decision: Decision, boot: BootstrapResult | None, reasons: list[str]) -> str:
    if decision == Decision.INVALID or boot is None:
        return "Comparison is INVALID: " + "; ".join(reasons or ["provenance mismatch"]) + "."
    pts = abs(boot.delta) * 100
    m = boot.policy.margin * 100
    lo, hi = boot.ci_low * 100, boot.ci_high * 100
    direction = "lower" if boot.delta < 0 else "higher"
    ci = f"[{lo:+.1f}, {hi:+.1f}] points"
    if decision == Decision.SIGNIFICANT_REGRESSION:
        return (
            f"Candidate is {pts:.1f} points {direction} than baseline and the {int((1 - boot.policy.alpha) * 100)}% CI "
            f"{ci} lies entirely beyond the allowed {m:.0f}-point margin. Meaningful regression."
        )
    if decision == Decision.SIGNIFICANT_IMPROVEMENT:
        return (
            f"Candidate is {pts:.1f} points higher than baseline and the CI {ci} excludes zero. "
            "Improvement supported by the evidence."
        )
    if decision == Decision.NO_MEANINGFUL_REGRESSION:
        if boot.delta < 0:
            return (
                f"Candidate is {pts:.1f} points lower than baseline, but the CI {ci} stays inside the allowed "
                f"{m:.0f}-point non-inferiority margin. No meaningful regression detected."
            )
        return (
            f"Candidate is {pts:.1f} points {direction} than baseline; CI {ci} stays inside the allowed "
            f"{m:.0f}-point margin. No meaningful regression detected."
        )
    return "Evidence is inconclusive. " + boot.reason + ". More independent cases or repeated samples are required."


def compare_runs(
    base_m: RunManifest,
    base: Sequence[SampleResult],
    cand_m: RunManifest,
    cand: Sequence[SampleResult],
    policy: BootstrapPolicy | None = None,
    mode: str = "strict",
    base_complete: bool = True,
    cand_complete: bool = True,
) -> Comparison:
    pol = policy or BootstrapPolicy()
    report = validate_pair(base_m, cand_m, list(base), list(cand), mode, base_complete, cand_complete)
    bs, cs = summarize(base), summarize(cand)
    if not report.valid:
        return Comparison(
            report, Decision.INVALID, None, None, bs, cs, explanation=explain(Decision.INVALID, None, report.reasons)
        )
    boot = paired_cluster_bootstrap(base, cand, pol)
    mc = mcnemar_exact(base, cand)
    bcat, ccat = category_rates(base), category_rates(cand)
    cat_deltas = {
        c: {
            "baseline": bcat[c]["rate"],
            "candidate": ccat[c]["rate"],
            "delta": (ccat[c]["rate"] - bcat[c]["rate"])
            if bcat[c]["rate"] is not None and ccat[c]["rate"] is not None
            else None,
            "n_baseline": bcat[c]["n"],
            "n_candidate": ccat[c]["n"],
        }
        for c in sorted(set(bcat) & set(ccat))
    }
    bf, cf = case_pass_fraction(base), case_pass_fraction(cand)
    first_b = {s.case_id: s for s in base if s.sample_index == 0}
    first_c = {s.case_id: s for s in cand if s.sample_index == 0}
    changes = []
    for cid in sorted(set(bf) & set(cf)):
        d = cf[cid] - bf[cid]
        if abs(d) > 1e-12:
            row: dict[str, Any] = {
                "case_id": cid,
                "baseline": bf[cid],
                "candidate": cf[cid],
                "delta": d,
                "kind": "improved" if d > 0 else "regressed",
                "category": (first_b.get(cid) or first_c[cid]).category,
            }
            if cid in first_b and cid in first_c:
                row["trajectory_diff"] = diff_trajectories(first_b[cid].result, first_c[cid].result)
            changes.append(row)
    newl = {
        k: v - bs["failure_labels"].get(k, 0)
        for k, v in cs["failure_labels"].items()
        if v > bs["failure_labels"].get(k, 0)
    }
    return Comparison(
        report, boot.decision, boot, mc, bs, cs, cat_deltas, changes, newl, explain(boot.decision, boot, [])
    )


@dataclass
class GateVerdict:
    passed: bool
    verdict: str  # pass | fail
    reasons: list[str]


def gate(comparison: Comparison, judge_ok: bool = True, conservative: bool = True) -> GateVerdict:
    """Release gate. Never weakened to make CI green: invalid/regression always block."""
    reasons: list[str] = []
    d = comparison.decision
    if d == Decision.INVALID:
        reasons.append("comparison is invalid: " + "; ".join(comparison.validity.reasons))
    if d == Decision.SIGNIFICANT_REGRESSION:
        reasons.append("statistically meaningful regression detected")
    if d == Decision.INCONCLUSIVE and conservative:
        reasons.append("evidence is inconclusive and the policy is conservative")
    if not judge_ok:
        reasons.append("a judge used for gating is not calibrated/admitted for its exact configuration")
    if not reasons:
        return GateVerdict(True, "pass", [comparison.explanation])
    return GateVerdict(False, "fail", reasons)
