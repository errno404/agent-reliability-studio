import math

import pytest
from evalcore.models import AgentResult, SampleResult, SampleStatus
from evalcore.stats import (
    BootstrapPolicy,
    Decision,
    classify_delta,
    mcnemar_exact,
    paired_cluster_bootstrap,
    percentile,
    repeated_run_stats,
    wilson_interval,
)


def S(case, idx, status, cat="a"):
    return SampleResult(case_id=case, category=cat, sample_index=idx, status=status, result=AgentResult())


P, F, E = SampleStatus.PASSED, SampleStatus.FAILED, SampleStatus.EXECUTION_ERROR


def run(rates, k=1, cat="a"):
    """rates: list of per-case numbers of passing samples out of k."""
    out = []
    for i, npass in enumerate(rates):
        for j in range(k):
            out.append(S(f"c{i}", j, P if j < npass else F, cat))
    return out


def test_wilson_known_value():
    lo, hi = wilson_interval(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3) and hi == pytest.approx(0.9433, abs=1e-3)


def test_wilson_edges():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and 0.69 < lo < 0.73
    with pytest.raises(ValueError):
        wilson_interval(3, 2)


def test_pass_hat_k_and_pass_at_k():
    # k=3: case0 3/3, case1 1/3 (flaky), case2 0/3, case3 3/3
    s = run([3, 1, 0, 3], k=3)
    r = repeated_run_stats(s)
    assert r.n_cases == 4 and r.n_samples == 12 and r.k == 3
    assert r.pass_hat_k == pytest.approx(0.5)  # 2 of 4 pass every repetition
    assert r.pass_at_k == pytest.approx(0.75)  # 3 of 4 pass at least once
    assert r.single_run_pass_rate == pytest.approx(7 / 12)
    assert r.flaky_cases == ["c1"] and r.flips_by_category == {"a": 1}
    assert r.pass_hat_k <= r.single_run_pass_rate <= r.pass_at_k


def test_execution_errors_excluded_from_quality():
    s = run([1, 1], k=1) + [S("c9", 0, E)]
    r = repeated_run_stats(s)
    assert r.n_cases == 2 and r.single_run_pass_rate == 1.0


def test_empty_and_all_fail():
    assert repeated_run_stats([]).n_cases == 0
    r = repeated_run_stats(run([0, 0, 0], k=2))
    assert r.pass_hat_k == 0 and r.pass_at_k == 0 and r.flaky_cases == []


def test_identical_runs_not_regression():
    b = run([1] * 40 + [0] * 20)
    res = paired_cluster_bootstrap(b, list(b), BootstrapPolicy(min_cases=50, n_boot=2000))
    assert res.delta == 0 and res.ci_low == 0 == res.ci_high
    assert res.decision == Decision.NO_MEANINGFUL_REGRESSION


def test_clear_regression_and_improvement():
    base = run([1] * 60)
    bad = run([0] * 30 + [1] * 30)
    pol = BootstrapPolicy(min_cases=50, n_boot=3000, margin=0.05)
    assert paired_cluster_bootstrap(base, bad, pol).decision == Decision.SIGNIFICANT_REGRESSION
    assert paired_cluster_bootstrap(bad, base, pol).decision == Decision.SIGNIFICANT_IMPROVEMENT


def test_too_few_cases_inconclusive():
    res = paired_cluster_bootstrap(run([1] * 10), run([0] * 10), BootstrapPolicy(min_cases=50, n_boot=500))
    assert res.decision == Decision.INCONCLUSIVE and "50" in res.reason


def test_no_matched_cases():
    a = [S("x", 0, P)]
    b = [S("y", 0, P)]
    assert paired_cluster_bootstrap(a, b).decision == Decision.INCONCLUSIVE


def test_bootstrap_is_deterministic_and_cluster_based():
    b = run([3, 2, 1, 0, 3, 3, 2, 1] * 8, k=3)
    c = run([3, 3, 1, 1, 3, 2, 2, 1] * 8, k=3)
    pol = BootstrapPolicy(min_cases=10, n_boot=2000)
    r1, r2 = paired_cluster_bootstrap(b, c, pol), paired_cluster_bootstrap(b, c, pol)
    assert r1 == r2 and r1.n_common_cases == 64


def test_small_drop_inside_margin_is_noninferior():
    # 4/100 cases flip pass->fail: delta -0.04, CI should sit inside a 0.10 margin
    base = run([1] * 100)
    cand = run([0] * 4 + [1] * 96)
    r = paired_cluster_bootstrap(base, cand, BootstrapPolicy(min_cases=50, n_boot=4000, margin=0.10))
    assert r.delta == pytest.approx(-0.04) and r.decision == Decision.NO_MEANINGFUL_REGRESSION


def test_classify_delta_table():
    assert classify_delta(0.01, 0.2, 0.05)[0] == Decision.SIGNIFICANT_IMPROVEMENT
    assert classify_delta(-0.3, -0.1, 0.05)[0] == Decision.SIGNIFICANT_REGRESSION
    assert classify_delta(-0.04, 0.02, 0.05)[0] == Decision.NO_MEANINGFUL_REGRESSION
    assert classify_delta(-0.2, 0.03, 0.05)[0] == Decision.INCONCLUSIVE
    # significant-but-tiny drop is inside margin => not a "regression"
    assert classify_delta(-0.04, -0.01, 0.05)[0] == Decision.NO_MEANINGFUL_REGRESSION


def test_mcnemar_exact():
    base = run([1] * 10 + [0] * 0)
    cand = run([0] * 8 + [1] * 2)
    m = mcnemar_exact(base, cand)
    assert (m.b, m.c) == (8, 0)
    assert m.p_value == pytest.approx(2 / 2**8)
    assert mcnemar_exact(base, base).p_value == 1.0


def test_percentile():
    assert percentile([], 95) == 0.0
    assert percentile([5], 95) == 5
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert math.isclose(percentile(list(range(101)), 95), 95)


def test_small_significant_drop_inside_margin_is_flagged_not_silent():
    from evalcore.stats import Decision, classify_delta

    d, why = classify_delta(-0.049, -0.001, 0.05)
    assert d == Decision.NO_MEANINGFUL_REGRESSION and "small regression is likely" in why
    d2, why2 = classify_delta(-0.01, 0.04, 0.05)
    assert d2 == Decision.NO_MEANINGFUL_REGRESSION and "likely" not in why2
