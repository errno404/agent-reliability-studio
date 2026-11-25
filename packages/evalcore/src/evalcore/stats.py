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
    """Repeated-run metrics over an EXPLICIT eligible cohort.

    * ``intended_k``: repetitions the run was supposed to have per case.
    * ``eligible_cases``: cases that have exactly ``intended_k`` usable (passed/failed) samples. ``pass_hat_k`` (all k
      pass) and ``pass_at_k`` (at least one passes) are BOTH computed over this same cohort and the same k.
    * ``excluded``: reason -> case ids that were left out (execution errors, missing repetitions, ...). Nothing is dropped
      silently; a hard case that crashed is reported as excluded, never as a pass.
    * ``mean_trial_pass_rate``: the average of individual trials over ALL usable samples (a mean over repeated trials, which
      is not the same quantity as a single run's pass rate). ``mean_trial_ci`` is a Wilson interval that treats trials as
      independent: it is optimistic because repetitions of one case are correlated; use the case-level bootstrap to decide.
    """

    n_cases: int  # cases with at least one usable sample
    n_samples: int  # usable samples
    k: int  # eligible k (== intended_k when given)
    intended_k: int
    eligible_cases: int
    excluded: dict[str, list[str]]
    mean_trial_pass_rate: float
    mean_trial_ci: tuple[float, float]
    pass_hat_k: float
    pass_at_k: float
    flaky_cases: list[str] = field(default_factory=list)
    flips_by_category: dict[str, int] = field(default_factory=dict)
    ci_method: str = "wilson_pooled_trials_ignores_case_clustering"

    @property
    def single_run_pass_rate(self) -> float:  # backwards-compatible alias; see mean_trial_pass_rate
        return self.mean_trial_pass_rate

    @property
    def single_run_ci(self) -> tuple[float, float]:
        return self.mean_trial_ci

    @property
    def n_excluded(self) -> int:
        return sum(len(v) for v in self.excluded.values())


def repeated_run_stats(
    samples: Sequence[SampleResult], intended_k: int | None = None, case_ids: Sequence[str] | None = None
) -> RepeatedRunStats:
    outs = per_case_outcomes(samples)
    cat = {s.case_id: s.category for s in samples}
    k = intended_k or max((len(v) for v in outs.values()), default=0)
    all_cases = list(case_ids) if case_ids is not None else sorted({s.case_id for s in samples})
    excluded: dict[str, list[str]] = {}
    status_of: dict[str, set[str]] = {}
    for s in samples:
        status_of.setdefault(s.case_id, set()).add(s.status.value)
    eligible: dict[str, list[bool]] = {}
    for c in all_cases:
        v = outs.get(c, [])
        if len(v) == k and k > 0:
            eligible[c] = v
            continue
        sts = status_of.get(c, set())
        reason = (
            "no_samples"
            if c not in status_of
            else "execution_error"
            if "execution_error" in sts
            else "invalid_or_skipped"
            if sts & {"invalid", "skipped"}
            else "missing_repetitions"
        )
        excluded.setdefault(reason, []).append(c)
    n_samples = sum(len(v) for v in outs.values())
    passes = sum(sum(v) for v in outs.values())
    flaky = sorted(c for c, v in eligible.items() if any(v) and not all(v))
    flips: dict[str, int] = defaultdict(int)
    for c in flaky:
        flips[cat.get(c, "?")] += 1
    ne = len(eligible)
    return RepeatedRunStats(
        n_cases=len(outs),
        n_samples=n_samples,
        k=k,
        intended_k=k,
        eligible_cases=ne,
        excluded=excluded,
        mean_trial_pass_rate=(passes / n_samples) if n_samples else 0.0,
        mean_trial_ci=wilson_interval(passes, n_samples) if n_samples else (0.0, 1.0),
        pass_hat_k=(sum(1 for v in eligible.values() if all(v)) / ne) if ne else 0.0,
        pass_at_k=(sum(1 for v in eligible.values() if any(v)) / ne) if ne else 0.0,
        flaky_cases=flaky,
        flips_by_category=dict(flips),
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
    max_missing_share: float = (
        0.0  # required observations that may be missing/errored/invalid before a release decision
    )

    def __post_init__(self) -> None:
        if self.n_boot < 100 or not 0 < self.alpha < 1 or self.margin < 0 or self.min_cases < 1:
            raise ValueError("invalid BootstrapPolicy (n_boot >= 100, 0 < alpha < 1, margin >= 0, min_cases >= 1)")
        if not 0 <= self.max_missing_share <= 1 or not 0 <= self.max_candidate_only_drop <= 1:
            raise ValueError("invalid BootstrapPolicy (shares must be within [0, 1])")


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
        if ci_high < 0:
            # a real but small drop that the policy margin tolerates: say so instead of passing silently
            return Decision.NO_MEANINGFUL_REGRESSION, (
                f"CI is entirely below zero but within the -{margin:.3f} margin: a small regression is likely and is tolerated by policy"
            )
        return Decision.NO_MEANINGFUL_REGRESSION, f"CI lower bound is within the -{margin:.3f} margin"
    return Decision.INCONCLUSIVE, "CI straddles the regression margin; more evidence needed"


def bootstrap_delta(b: dict[str, float], c: dict[str, float], pol: BootstrapPolicy) -> tuple[float, float, float, int]:
    """Case-level paired bootstrap of mean(c - b) over cases present in both mappings -> (delta, lo, hi, n)."""
    common = sorted(set(b) & set(c))
    n = len(common)
    if n == 0:
        return 0.0, -1.0, 1.0, 0
    deltas = [c[i] - b[i] for i in common]
    rng = random.Random(pol.seed)
    means = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(pol.n_boot))
    lo_i = int(math.floor((pol.alpha / 2) * pol.n_boot))
    hi_i = int(math.ceil((1 - pol.alpha / 2) * pol.n_boot)) - 1
    return sum(deltas) / n, means[max(0, lo_i)], means[min(pol.n_boot - 1, hi_i)], n


def end_to_end_fractions(samples: Iterable[SampleResult], case_ids: Sequence[str], k: int) -> dict[str, float]:
    """Per-case pass fraction over the INTENDED k observations: errored, invalid, skipped and missing count as FAILURES.

    This is the conservative sensitivity analysis: it answers 'what if every unusable observation had failed?' so that
    selective missingness cannot manufacture an improvement.
    """
    passes: dict[str, int] = defaultdict(int)
    for s in samples:
        if s.status == SampleStatus.PASSED:
            passes[s.case_id] += 1
    return {cid: min(passes.get(cid, 0), k) / k for cid in case_ids}


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
