"""Statistics: Wilson intervals, clustered paired bootstrap, McNemar, pass^k / pass@k.

Statistical unit = the *case*. Repeated samples of one case are correlated, so they
are first reduced to a per-case pass fraction and the bootstrap resamples *cases*,
never raw samples. Execution errors are excluded from quality metrics (they are
reported separately) so infrastructure failures never masquerade as wrong answers.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from .models import SampleResult, SampleStatus

Z_95 = 1.959963984540054


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. ``n == 0`` -> (0, 1) (no information)."""
    if n <= 0:
        return 0.0, 1.0
    if not 0 <= successes <= n:
        raise ValueError("successes must be within [0, n]")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _quality(samples: Iterable[SampleResult]) -> list[SampleResult]:
    return [s for s in samples if s.status in (SampleStatus.PASSED, SampleStatus.FAILED)]


def per_case_outcomes(samples: Iterable[SampleResult]) -> dict[str, list[bool]]:
    out: dict[str, list[bool]] = defaultdict(list)
    for s in _quality(samples):
        out[s.case_id].append(s.status == SampleStatus.PASSED)
    return dict(out)


@dataclass(frozen=True)
class RepeatedRunStats:
    n_cases: int
    n_samples: int
    k: int  # min samples per case actually used
    single_run_pass_rate: float
    single_run_ci: tuple[float, float]
    pass_hat_k: float  # pass^k: passes EVERY repetition (reliability)
    pass_at_k: float  # passes AT LEAST ONCE (capability)
    flaky_cases: list[str] = field(default_factory=list)
    flips_by_category: dict[str, int] = field(default_factory=dict)


def repeated_run_stats(samples: Sequence[SampleResult]) -> RepeatedRunStats:
    """Single-run pass rate, pass^k, pass@k and flaky detection.

    pass^k uses the cases' full repetition set; cases with differing numbers of usable
    samples are compared on what they have (k reported as the minimum).
    """
    outs = per_case_outcomes(samples)
    cat = {s.case_id: s.category for s in samples}
    n_cases = len(outs)
    if n_cases == 0:
        return RepeatedRunStats(0, 0, 0, 0.0, (0.0, 1.0), 0.0, 0.0)
    n_samples = sum(len(v) for v in outs.values())
    passes = sum(sum(v) for v in outs.values())
    full = max(len(v) for v in outs.values())
    complete = {c: v for c, v in outs.items() if len(v) == full}  # pass^k needs the same k for every case
    pass_all = sum(1 for v in complete.values() if all(v))
    pass_any = sum(1 for v in outs.values() if any(v))
    flaky = sorted(c for c, v in outs.items() if any(v) and not all(v))
    flips: dict[str, int] = defaultdict(int)
    for c in flaky:
        flips[cat[c]] += 1
    return RepeatedRunStats(
        n_cases,
        n_samples,
        full,
        passes / n_samples,
        wilson_interval(passes, n_samples),
        pass_all / len(complete),
        pass_any / n_cases,
        flaky,
        dict(flips),
    )


def case_pass_fraction(samples: Iterable[SampleResult]) -> dict[str, float]:
    return {c: sum(v) / len(v) for c, v in per_case_outcomes(samples).items() if v}


class Decision(StrEnum):
    SIGNIFICANT_REGRESSION = "significant_regression"
    SIGNIFICANT_IMPROVEMENT = "significant_improvement"
    NO_MEANINGFUL_REGRESSION = "no_meaningful_regression"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


@dataclass(frozen=True)
class BootstrapPolicy:
    min_cases: int = 50
    alpha: float = 0.05
    n_boot: int = 10_000
    margin: float = 0.05  # practical non-inferiority margin (absolute pass-rate points)
    seed: int = 20260101
    max_candidate_only_drop: float = 0.05  # candidate-only dropped cases (errors) above this share => inconclusive

    def __post_init__(self) -> None:
        if self.n_boot < 100 or not 0 < self.alpha < 1 or self.margin < 0 or self.min_cases < 1:
            raise ValueError("invalid BootstrapPolicy (n_boot >= 100, 0 < alpha < 1, margin >= 0, min_cases >= 1)")


@dataclass(frozen=True)
class BootstrapResult:
    decision: Decision
    delta: float
    ci_low: float
    ci_high: float
    n_common_cases: int
    n_improved: int
    n_regressed: int
    n_unchanged: int
    baseline_rate: float
    candidate_rate: float
    reason: str
    policy: BootstrapPolicy


def classify_delta(ci_low: float, ci_high: float, margin: float) -> tuple[Decision, str]:
    """Map a delta CI (candidate - baseline) to a decision.

    * improvement:   CI entirely above 0
    * regression:    CI entirely below -margin (a drop larger than the practical margin, with confidence)
    * no meaningful regression (non-inferior): CI lower bound >= -margin
    * otherwise inconclusive. "Not significant" is NOT treated as "equivalent".
    """
    if ci_low > 0:
        return Decision.SIGNIFICANT_IMPROVEMENT, "CI is entirely above zero"
    if ci_high < -margin:
        return Decision.SIGNIFICANT_REGRESSION, f"CI is entirely below the -{margin:.3f} margin"
    if ci_low >= -margin:
        return Decision.NO_MEANINGFUL_REGRESSION, f"CI lower bound is within the -{margin:.3f} margin"
    return Decision.INCONCLUSIVE, "CI straddles the regression margin; more evidence needed"


def paired_cluster_bootstrap(
    baseline: Sequence[SampleResult],
    candidate: Sequence[SampleResult],
    policy: BootstrapPolicy | None = None,
) -> BootstrapResult:
    """Case-level paired bootstrap of (candidate - baseline) pass rate.

    1. reduce each case to its mean pass fraction (preserves within-case correlation);
    2. match cases present in both runs;
    3. resample matched cases with replacement ``n_boot`` times;
    4. percentile CI of the mean delta; apply the practical margin.
    """
    pol = policy or BootstrapPolicy()
    b, c = case_pass_fraction(baseline), case_pass_fraction(candidate)
    common = sorted(set(b) & set(c))
    n = len(common)
    deltas = [c[i] - b[i] for i in common]
    if n == 0:
        return BootstrapResult(Decision.INCONCLUSIVE, 0.0, -1.0, 1.0, 0, 0, 0, 0, 0.0, 0.0, "no matched cases", pol)
    brate = sum(b[i] for i in common) / n
    crate = sum(c[i] for i in common) / n
    delta = crate - brate
    imp = sum(1 for d in deltas if d > 1e-12)
    reg = sum(1 for d in deltas if d < -1e-12)
    rng = random.Random(pol.seed)
    means = []
    for _ in range(pol.n_boot):
        means.append(sum(deltas[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo_i = int(math.floor((pol.alpha / 2) * pol.n_boot))
    hi_i = int(math.ceil((1 - pol.alpha / 2) * pol.n_boot)) - 1
    lo, hi = means[max(0, lo_i)], means[min(pol.n_boot - 1, hi_i)]
    lost_in_candidate = set(b) - set(c)  # cases the candidate has no quality samples for (e.g. it crashed on them)
    if b and len(lost_in_candidate) / len(b) > pol.max_candidate_only_drop:
        return BootstrapResult(
            Decision.INCONCLUSIVE,
            delta,
            lo,
            hi,
            n,
            imp,
            reg,
            n - imp - reg,
            brate,
            crate,
            f"candidate has no usable samples for {len(lost_in_candidate)} of {len(b)} baseline cases "
            "(execution errors); the matched cases may be the easy ones",
            pol,
        )
    if n < pol.min_cases:
        return BootstrapResult(
            Decision.INCONCLUSIVE,
            delta,
            lo,
            hi,
            n,
            imp,
            reg,
            n - imp - reg,
            brate,
            crate,
            f"only {n} matched cases; policy requires >= {pol.min_cases}",
            pol,
        )
    dec, why = classify_delta(lo, hi, pol.margin)
    return BootstrapResult(dec, delta, lo, hi, n, imp, reg, n - imp - reg, brate, crate, why, pol)


@dataclass(frozen=True)
class McNemarResult:
    b: int  # baseline pass, candidate fail
    c: int  # baseline fail, candidate pass
    p_value: float
    note: str = "diagnostic only; not used as the regression decision"


def mcnemar_exact(baseline: Sequence[SampleResult], candidate: Sequence[SampleResult]) -> McNemarResult:
    """Exact two-sided McNemar on matched cases using per-case majority outcome."""
    bo, co = per_case_outcomes(baseline), per_case_outcomes(candidate)
    b = c = 0
    for case in set(bo) & set(co):
        bp, cp = sum(bo[case]) * 2 > len(bo[case]), sum(co[case]) * 2 > len(co[case])
        if bp and not cp:
            b += 1
        elif cp and not bp:
            c += 1
    n = b + c
    if n == 0:
        return McNemarResult(0, 0, 1.0)
    k = min(b, c)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)
    return McNemarResult(b, c, p)


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile (q in [0,100]); 0.0 for empty input."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)
