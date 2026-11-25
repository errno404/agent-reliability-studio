"""Strict provenance, comparison intent, selective missingness and the release gate."""

import pytest
from evalcore import BootstrapPolicy, Decision, SampleStatus, compare_runs, gate, validate_pair
from evalcore.models import AgentResult, SampleResult
from evalcore.stats import repeated_run_stats
from test_core import E, F, P, man, many, samp

IDS = [f"c{i}" for i in range(60)]
POL = BootstrapPolicy(min_cases=20, n_boot=800, margin=0.05)


def run(m_base=None, m_cand=None, base=None, cand=None, **kw):
    mb = m_base or man(case_ids=IDS)
    mc = m_cand or man(case_ids=IDS, agent_version="v2")
    return compare_runs(mb, base or many(60, lambda i, j: True), mc, cand or many(60, lambda i, j: True), POL, **kw)


def live(sample_model="claude-x", **kw):
    return man(
        case_ids=IDS, execution_kind="live", model="haiku", model_resolved="claude-x", model_provider="anthropic", **kw
    )


def lsamp(cid, status=P, model="claude-x"):
    return SampleResult(
        case_id=cid,
        category="c",
        sample_index=0,
        status=status,
        result=AgentResult(model=model, metadata={"execution_kind": "live"}),
    )


def test_synthetic_and_live_runs_are_never_comparable_even_exploratory():
    c = run(man(case_ids=IDS), live(), mode="exploratory")
    assert c.decision == Decision.INVALID and any("execution_kind" in r for r in c.validity.reasons)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fixture_hash", "other"),
        ("evaluator_hash", "e2"),
        ("rubric_hash", "r2"),
        ("tool_schema_hash", "t2"),
        ("model", "m2"),
        ("model_params", {"temperature": 1}),
    ],
)
def test_prompt_or_agent_change_requires_every_other_variable_controlled(field, value):
    c = run(m_cand=man(case_ids=IDS, agent_version="v2", **{field: value}), intent="agent_change")
    assert c.decision == Decision.INVALID, field


def test_intent_allows_exactly_the_declared_variable_and_records_it():
    ok = run(m_cand=man(case_ids=IDS, model="m2"), intent="model_change")
    assert ok.decision != Decision.INVALID and any("model differs as intended" in w for w in ok.validity.warnings)
    bad = run(m_cand=man(case_ids=IDS, model="m2", tool_schema_hash="t2"), intent="model_change")
    assert bad.decision == Decision.INVALID  # tools changed too: not a clean model comparison
    assert run(m_cand=man(case_ids=IDS, tool_schema_hash="t2"), intent="tool_change").decision != Decision.INVALID
    assert run(m_cand=man(case_ids=IDS, evaluator_hash="e2"), intent="evaluator_change").decision != Decision.INVALID
    assert run(intent="no_such_intent").decision == Decision.INVALID


def test_unknown_evaluator_identity_is_refused_in_strict_mode():
    c = run(m_base=man(case_ids=IDS, evaluator_hash=""))
    assert c.decision == Decision.INVALID and any("evaluator_unknown" in r for r in c.validity.reasons)


def test_alias_drift_is_detected_from_sample_metadata():
    base = [lsamp(c) for c in IDS]
    cand = [lsamp(c, model="claude-y") for c in IDS]  # provider silently served a different model
    c = compare_runs(live(), base, live(agent_version="v2"), cand, POL)
    assert c.decision == Decision.INVALID and any("model_alias_drift" in r for r in c.validity.reasons)


def test_samples_must_match_manifest_execution_kind():
    base = [lsamp(c) for c in IDS]
    cand = [
        SampleResult(case_id=c, category="c", sample_index=0, status=P, result=AgentResult(model="claude-x"))
        for c in IDS
    ]
    cand[0].result.metadata["execution_kind"] = "synthetic"
    assert any("execution_kind" in r for r in validate_pair(live(), live(agent_version="v2"), base, cand).reasons)


def test_gate_refuses_exploratory_invalid_and_empty_comparisons():
    imp = run(base=many(60, lambda i, j: i >= 30), cand=many(60, lambda i, j: True))
    assert gate(imp, judge_ok=True).passed and gate(imp, judge_ok=True).authorizes_release
    expl = run(base=many(60, lambda i, j: i >= 30), cand=many(60, lambda i, j: True), mode="exploratory")
    g = gate(expl, judge_ok=True)
    assert not g.passed and any("only strict" in r for r in g.reasons) and not g.authorizes_release
    diag = gate(imp, judge_ok=True, release=False)
    assert diag.passed and not diag.authorizes_release  # research mode can never authorise
    empty = compare_runs(man(case_ids=["a"]), [], man(case_ids=["a"], agent_version="v2"), [], POL)
    assert not gate(empty, judge_ok=True).passed


def test_incomplete_required_evidence_forces_inconclusive_even_when_the_visible_delta_is_good():
    base = many(60, lambda i, j: i >= 30)
    cand = [samp(f"c{i}", 0, P if i < 55 else E) for i in range(60)]  # candidate crashes on 5 of the "hard" cases
    c = run(base=base, cand=cand)
    assert c.decision == Decision.INCONCLUSIVE and c.incomplete_reasons and not gate(c, judge_ok=True).passed
    assert c.end_to_end and c.end_to_end["n_cases"] == 60  # sensitivity analysis counts crashes as failures


def test_end_to_end_sensitivity_exposes_selective_missingness():
    # candidate crashes on 10 of the 60 cases the baseline passes. Conditional on executing it looks perfect (delta 0)
    # but counting crashes as failures shows a real operational regression: selective missingness cannot hide it.
    base = many(60, lambda i, j: True)
    cand = [samp(f"c{i}", 0, P if i < 50 else E) for i in range(60)]
    c = run(base=base, cand=cand)
    assert c.bootstrap is not None and c.end_to_end is not None
    assert (
        c.bootstrap.delta == pytest.approx(0.0) or c.decision == Decision.INCONCLUSIVE
    )  # conditional view alone is misleading
    assert c.end_to_end["delta"] == pytest.approx(-10 / 60)
    assert c.end_to_end["decision"] == Decision.SIGNIFICANT_REGRESSION.value
    g = gate(c, judge_ok=True)
    assert not g.passed and any("sensitivity analysis" in r or "incomplete" in r for r in g.reasons)
    assert c.coverage["candidate"]["execution_error"] == 10


def test_one_sided_noninferiority_wording_never_claims_equivalence():
    pol = BootstrapPolicy(min_cases=20, n_boot=800, margin=0.10)
    c = compare_runs(
        man(case_ids=IDS),
        many(60, lambda i, j: True),
        man(case_ids=IDS, agent_version="v2"),
        many(60, lambda i, j: i >= 1),
        pol,
    )
    assert c.decision == Decision.NO_MEANINGFUL_REGRESSION
    assert "one-sided non-inferiority" in c.explanation and "not a claim of equivalence" in c.explanation
    assert "entirely inside" not in c.explanation  # a one-sided boundary is not a two-sided equivalence band


def test_repeated_run_metrics_use_one_explicit_eligible_cohort():
    s = []
    for cid, outs in (("a", "PPP"), ("b", "PFP"), ("c", "FFF"), ("d", "PP"), ("e", "PEP")):
        for i, ch in enumerate(outs):
            s.append(samp(cid, i, {"P": P, "F": F, "E": E}[ch]))
    r = repeated_run_stats(s, intended_k=3, case_ids=list("abcdef"))
    assert (r.intended_k, r.k, r.eligible_cases) == (3, 3, 3)  # a, b, c have all 3 usable repetitions
    assert r.excluded == {"missing_repetitions": ["d"], "execution_error": ["e"], "no_samples": ["f"]}
    assert r.pass_hat_k == pytest.approx(1 / 3) and r.pass_at_k == pytest.approx(2 / 3) and r.flaky_cases == ["b"]
    assert r.pass_hat_k <= r.pass_at_k
    assert r.mean_trial_pass_rate == pytest.approx(9 / 13) and "ignores_case_clustering" in r.ci_method


def test_operational_reliability_is_reported_separately_from_quality():
    from evalcore import summarize

    s = [samp("a", 0, P), samp("b", 0, F), samp("c", 0, E), samp("d", 0, E)]
    m = summarize(s, 1, list("abcd"))
    assert m["execution_success_rate"] == pytest.approx(0.5)
    assert m["conditional_quality_rate"] == pytest.approx(0.5) and m["end_to_end_success_rate"] == pytest.approx(0.25)
    assert m["excluded_cases"] == 2 and m["exclusion_reasons"] == {"execution_error": 2}


def test_status_enum_has_no_silent_success_for_unusable_samples():
    assert SampleStatus.EXECUTION_ERROR.value == "execution_error"


def _judge_case(required):
    from evalcore.models import AssertionSpec, Case

    return Case(
        id="j",
        title="t",
        category="c",
        description="d",
        input="q",
        assertions=[AssertionSpec.model_validate({"type": "output_contains", "value": "x"})],
        rubric={"judge": {"must": ["a"], "required": required, "gating": True}},
    )


def test_required_judge_missing_or_unadmitted_is_invalid_not_silently_skipped():
    from evalcore.judge import HeuristicJudge, Judge, JudgeConfig
    from evalcore.runner import score_result

    r = AgentResult(final_output="x a")
    none = score_result(_judge_case(True), r)
    assert none.status == SampleStatus.INVALID and any(
        a.invalid and "required judge" in a.evidence for a in none.assertions
    )
    j = Judge(HeuristicJudge(), JudgeConfig(backend="heuristic", model="m"))
    unadmitted = score_result(_judge_case(True), r, judge=j, judge_admitted=False)
    assert unadmitted.status == SampleStatus.INVALID
    assert score_result(_judge_case(False), r).status == SampleStatus.PASSED  # optional/diagnostic criterion
    assert score_result(_judge_case(True), r, judge=j, judge_admitted=True).status == SampleStatus.PASSED


def test_judge_identity_covers_generation_settings_and_rubric():
    from evalcore.calibration import judge_identity

    base = judge_identity("litellm", "m", "p", "cfg-a")
    assert judge_identity("litellm", "m", "p", "cfg-b") != base  # temperature / rubric / parser changed
    assert judge_identity("litellm", "m", "p", "cfg-a") == base


def test_release_eligibility_needs_trusted_labels_and_a_false_positive_confidence_bound():
    from evalcore.calibration import admit, calibration_metrics, fpr_upper_bound, release_eligibility

    pred = [True] * 30 + [False] * 30
    ref = [True] * 30 + [False] * 30  # perfect judge: 0 false positives on 30 negatives
    m = calibration_metrics(pred, ref)
    adm = admit(m)
    assert adm.admitted and fpr_upper_bound(m) > 0.10  # 0/30 is still consistent with an ~11% true FPR
    synth = release_eligibility(adm.admitted, m, {"synthetic_fixture": 60})
    assert not synth.eligible and synth.scope == "demonstration" and any("synthetic" in r for r in synth.reasons)
    human = release_eligibility(adm.admitted, m, {"human": 60})
    assert not human.eligible and any("upper bound" in r for r in human.reasons)  # trusted labels, but n too small
    big = calibration_metrics([True] * 100 + [False] * 100, [True] * 100 + [False] * 100)
    assert release_eligibility(admit(big).admitted, big, {"human": 100, "adjudicated": 100}).eligible
