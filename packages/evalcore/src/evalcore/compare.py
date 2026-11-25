"""Baseline vs candidate comparison, with plain-language explanation and the release gate.

Two ideas are kept strictly apart:

* **analysis** (`compare_runs`): produces evidence in either `strict` or `exploratory` mode;
* **authorization** (`gate(..., release=True)`): only a *strict*, *valid*, *non-empty*, *complete-evidence* comparison with
  *release-eligible judges* can be authorised. Exploratory output can never authorise a release.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .manifest import DEFAULT_INTENT, RunManifest, ValidationReport, validate_pair
from .models import SampleResult
from .stats import (
    BootstrapPolicy,
    BootstrapResult,
    Decision,
    McNemarResult,
    bootstrap_delta,
    case_pass_fraction,
    classify_delta,
    end_to_end_fractions,
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
    mode: str = "strict"
    intent: str = DEFAULT_INTENT
    end_to_end: dict[str, Any] | None = None  # sensitivity analysis: unusable observations counted as failures
    coverage: dict[str, Any] = field(default_factory=dict)
    incomplete_reasons: list[str] = field(default_factory=list)


def explain(decision: Decision, boot: BootstrapResult | None, reasons: list[str]) -> str:
    if decision == Decision.INVALID or boot is None:
        return "Comparison is INVALID: " + "; ".join(reasons or ["provenance mismatch"]) + "."
    pts = abs(boot.delta) * 100
    m = boot.policy.margin * 100
    lo, hi = boot.ci_low * 100, boot.ci_high * 100
    direction = "lower" if boot.delta < 0 else "higher"
    ci = f"[{lo:+.1f}, {hi:+.1f}] points"
    conf = int((1 - boot.policy.alpha) * 100)
    if decision == Decision.SIGNIFICANT_REGRESSION:
        return (
            f"Candidate is {pts:.1f} points {direction} than baseline; the {conf}% CI {ci} lies entirely below the "
            f"−{m:.0f}-point non-inferiority boundary. Meaningful regression."
        )
    if decision == Decision.SIGNIFICANT_IMPROVEMENT:
        return f"Candidate is {pts:.1f} points higher than baseline and the {conf}% CI {ci} lies entirely above zero."
    if decision == Decision.NO_MEANINGFUL_REGRESSION:
        return (
            f"Candidate is {pts:.1f} points {direction} than baseline. The lower bound of the {conf}% CI ({lo:+.1f}) is above "
            f"the −{m:.0f}-point non-inferiority boundary, so a drop larger than the margin is not supported by the data. "
            "This is a one-sided non-inferiority conclusion, not a claim of equivalence."
        )
    return (
        "Evidence is inconclusive. "
        + boot.reason
        + ". More independent cases, complete repetitions or fewer execution errors are required."
    )


def compare_runs(
    base_m: RunManifest,
    base: Sequence[SampleResult],
    cand_m: RunManifest,
    cand: Sequence[SampleResult],
    policy: BootstrapPolicy | None = None,
    mode: str = "strict",
    base_complete: bool = True,
    cand_complete: bool = True,
    intent: str = DEFAULT_INTENT,
) -> Comparison:
    pol = policy or BootstrapPolicy()
    report = validate_pair(base_m, cand_m, list(base), list(cand), mode, base_complete, cand_complete, intent)
    bs = summarize(base, base_m.samples_per_case, base_m.case_ids)
    cs = summarize(cand, cand_m.samples_per_case, cand_m.case_ids)
    if not report.valid:
        return Comparison(
            report,
            Decision.INVALID,
            None,
            None,
            bs,
            cs,
            explanation=explain(Decision.INVALID, None, report.reasons),
            mode=mode,
            intent=intent,
            coverage=report.coverage,
        )
    boot = paired_cluster_bootstrap(base, cand, pol)
    # Sensitivity: unusable observations (errors / missing / invalid / skipped) counted as FAILURES, over the intended k.
    common_ids = sorted(set(base_m.case_ids) & set(cand_m.case_ids))
    k = max(base_m.samples_per_case, 1)
    e_delta, e_lo, e_hi, e_n = bootstrap_delta(
        end_to_end_fractions(base, common_ids, k), end_to_end_fractions(cand, common_ids, k), pol
    )
    e2e = {
        "delta": e_delta,
        "ci_low": e_lo,
        "ci_high": e_hi,
        "n_cases": e_n,
        "decision": classify_delta(e_lo, e_hi, pol.margin)[0].value if e_n else Decision.INCONCLUSIVE.value,
        "note": "unusable observations counted as failures (conservative sensitivity analysis)",
    }
    incomplete: list[str] = []
    for label, c in (
        ("baseline", report.coverage.get("baseline", {})),
        ("candidate", report.coverage.get("candidate", {})),
    ):
        if c.get("incomplete_share", 0.0) > pol.max_missing_share:
            incomplete.append(
                f"{label}: {c['incomplete']}/{c['expected']} required observations missing, errored, invalid or skipped "
                f"(policy allows {pol.max_missing_share:.0%})"
            )
    decision, reason = boot.decision, boot.reason
    if incomplete and decision != Decision.INCONCLUSIVE:
        # Incomplete required evidence can never yield an authoritative verdict.
        decision, reason = Decision.INCONCLUSIVE, "required evidence is incomplete: " + "; ".join(incomplete)
        from dataclasses import replace

        boot = replace(boot, decision=decision, reason=reason)
    elif incomplete:
        reason = boot.reason + "; also " + "; ".join(incomplete)
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
        k2: v - bs["failure_labels"].get(k2, 0)
        for k2, v in cs["failure_labels"].items()
        if v > bs["failure_labels"].get(k2, 0)
    }
    return Comparison(
        report,
        decision,
        boot,
        mcnemar_exact(base, cand),
        bs,
        cs,
        cat_deltas,
        changes,
        newl,
        explain(decision, boot, []),
        mode,
        intent,
        e2e,
        report.coverage,
        incomplete,
    )


@dataclass
class GateVerdict:
    passed: bool
    verdict: str  # pass | fail
    reasons: list[str]
    authorizes_release: bool = False  # True ONLY for a strict, release-grade pass


def gate(comparison: Comparison, *, judge_ok: bool, release: bool = True) -> GateVerdict:
    """Release gate. ``judge_ok`` is REQUIRED (no implicit approval).

    ``release=True`` (default) enforces everything a release needs: strict mode, valid provenance, a non-empty matched set,
    complete required evidence, release-eligible judges, and a verdict of improvement or no-meaningful-regression.
    ``release=False`` is research/diagnostic: it reports what the verdict would be but ``authorizes_release`` stays False.
    Thresholds are never relaxed to turn a gate green.
    """
    reasons: list[str] = []
    d = comparison.decision
    b = comparison.bootstrap
    if comparison.mode != "strict":
        reasons.append(f"comparison mode is '{comparison.mode}'; only strict comparisons can authorise a release")
    if d == Decision.INVALID or not comparison.validity.valid:
        reasons.append("comparison is invalid: " + "; ".join(comparison.validity.reasons or ["provenance mismatch"]))
    elif b is None or b.n_common_cases == 0:
        reasons.append("comparison is empty: no matched cases")
    if d == Decision.SIGNIFICANT_REGRESSION:
        reasons.append("statistically meaningful regression detected")
    if d == Decision.INCONCLUSIVE:
        reasons.append("evidence is inconclusive: " + (b.reason if b else "no statistics"))
    if comparison.incomplete_reasons:
        reasons.append("required evidence is incomplete: " + "; ".join(comparison.incomplete_reasons))
    e2e = comparison.end_to_end
    if e2e and e2e.get("decision") == Decision.SIGNIFICANT_REGRESSION.value and d != Decision.SIGNIFICANT_REGRESSION:
        reasons.append("sensitivity analysis (unusable observations counted as failures) indicates a regression")
    if not judge_ok:
        reasons.append(
            "a judge used for gating is not release-eligible (needs a current admission backed by trusted human or "
            "adjudicated labels and a confidence bound on false positives)"
        )
    ok = not reasons and d in (Decision.SIGNIFICANT_IMPROVEMENT, Decision.NO_MEANINGFUL_REGRESSION)
    if ok:
        return GateVerdict(True, "pass", [comparison.explanation], authorizes_release=release)
    return GateVerdict(False, "fail", reasons or ["no authorising verdict"], False)
