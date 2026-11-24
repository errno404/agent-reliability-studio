"""Run-level metrics. Each scoring layer is reported separately; there is no blended score."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from .models import Layer, SampleResult, SampleStatus
from .stats import percentile, repeated_run_stats, wilson_interval


def _rate(samples: Sequence[SampleResult], layer: Layer | None) -> dict[str, Any]:
    vals: list[bool] = []
    for s in samples:
        if not s.counts_for_quality:
            continue
        v = (s.status == SampleStatus.PASSED) if layer is None else s.layer_pass(layer)
        if v is not None:
            vals.append(v)
    n, k = len(vals), sum(vals)
    lo, hi = wilson_interval(k, n)
    return {"rate": (k / n) if n else None, "n": n, "passed": k, "ci_low": lo, "ci_high": hi}


def summarize(
    samples: Sequence[SampleResult], intended_k: int | None = None, case_ids: Sequence[str] | None = None
) -> dict[str, Any]:
    quality = [s for s in samples if s.counts_for_quality]
    rr = repeated_run_stats(list(samples), intended_k, case_ids)
    lat = [s.result.latency_ms for s in quality]
    costs = [s.result.cost_usd for s in quality]
    cost_known = bool(costs) and all(c is not None for c in costs)
    return {
        "n_samples": len(samples),
        "n_cases": len({s.case_id for s in samples}),
        "status_counts": dict(Counter(s.status.value for s in samples)),
        "task_success": _rate(samples, None),
        "outcome": _rate(samples, Layer.OUTCOME),
        "trajectory": _rate(samples, Layer.TRAJECTORY),
        "component": _rate(samples, Layer.COMPONENT),
        "policy": _rate(samples, Layer.POLICY),
        "execution_error_rate": (sum(1 for s in samples if s.status == SampleStatus.EXECUTION_ERROR) / len(samples))
        if samples
        else 0.0,
        "latency_p50_ms": percentile(lat, 50),
        "latency_p95_ms": percentile(lat, 95),
        "total_tokens": sum(s.result.total_tokens for s in quality),
        "input_tokens": sum(s.result.input_tokens for s in quality),
        "output_tokens": sum(s.result.output_tokens for s in quality),
        "cost_usd": round(sum(c for c in costs if c is not None), 6) if cost_known else None,
        "cost_label": "API-equivalent estimated cost" if cost_known else "pricing unavailable",
        "pass_hat_k": rr.pass_hat_k,
        "pass_at_k": rr.pass_at_k,
        "k": rr.k,
        "intended_k": rr.intended_k,
        "eligible_cases": rr.eligible_cases,
        "excluded_cases": rr.n_excluded,
        "exclusion_reasons": {reason: len(ids) for reason, ids in rr.excluded.items()},
        "excluded_case_ids": {reason: ids[:10] for reason, ids in rr.excluded.items()},
        # mean of individual trials (NOT a single run's pass rate); Wilson CI treats trials as independent => optimistic
        "mean_trial_pass_rate": rr.mean_trial_pass_rate,
        "mean_trial_ci": list(rr.mean_trial_ci),
        "mean_trial_ci_method": rr.ci_method,
        "single_run_pass_rate": rr.mean_trial_pass_rate,  # deprecated alias
        "single_run_ci": list(rr.mean_trial_ci),  # deprecated alias
        # operational reliability is reported SEPARATELY from agent quality
        "execution_success_rate": (
            1
            - ((sum(1 for s in samples if s.status == SampleStatus.EXECUTION_ERROR) / len(samples)) if samples else 0.0)
        ),
        "conditional_quality_rate": _rate(samples, None)["rate"],  # pass rate among samples that executed
        "end_to_end_success_rate": (sum(1 for s in samples if s.status == SampleStatus.PASSED) / len(samples))
        if samples
        else 0.0,
        "flaky_cases": rr.flaky_cases,
        "flips_by_category": rr.flips_by_category,
        "failure_labels": dict(Counter(lab for s in samples for lab in s.failure_labels)),
    }


def category_rates(samples: Sequence[SampleResult]) -> dict[str, dict[str, Any]]:
    cats: dict[str, list[SampleResult]] = {}
    for s in samples:
        cats.setdefault(s.category, []).append(s)
    return {c: _rate(v, None) for c, v in sorted(cats.items())}
