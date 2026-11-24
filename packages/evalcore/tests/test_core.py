import json
import textwrap
from typing import Any

import pytest
from conftest import mk
from evalcore import (
    AdmissionPolicy,
    BootstrapPolicy,
    CallableAdapter,
    Decision,
    RunManifest,
    SampleStatus,
    admit,
    calibration_metrics,
    cohens_kappa,
    compare_runs,
    dataset_hash,
    execute_run,
    find_disagreements,
    gate,
    load_and_validate,
    mean_pairwise_kappa,
    score_result,
    validate_pair,
)
from evalcore.dataset import DatasetError, load_dataset, validate_dataset
from evalcore.distill import distill_case
from evalcore.judge import (
    HeuristicJudge,
    Judge,
    JudgeConfig,
    MalformedJudgeOutput,
    ScriptedBackend,
    parse_verdict,
)
from evalcore.models import AgentResult, AssertionSpec, Case, Dataset, Layer, SampleResult, ToolCall
from evalcore.redaction import REDACTED, Redactor
from evalcore.runner import RunContext
from evalcore.taxonomy import TAXONOMY, classify_failure
from evalcore.tracing import TraceRecorder
from evalcore.trajectory import diff_trajectories, trajectory_checks

YAML = textwrap.dedent("""
    name: demo
    version: v1
    kind: support
    fixture_version: f1
    cases:
      - id: a1
        title: A
        category: refund
        description: why a1 exists
        input: refund please
        assertions:
          - {type: output_contains, value: refund}
""")


def write(tmp_path, text):
    p = tmp_path / "d.yaml"
    p.write_text(text)
    return p


# ------------------------------------------------------------ datasets ----
def test_dataset_hash_changes_with_any_evidence(tmp_path):
    ds, h = load_and_validate(write(tmp_path, YAML))
    assert len(h) == 16
    variants = [YAML.replace("value: refund}", "value: refunded}"),            # assertion / expected
                YAML.replace("fixture_version: f1", "fixture_version: f2"),      # fixture version
                YAML.replace("refund please", "refund pls")]                     # case definition
    for v in variants:
        assert load_and_validate(write(tmp_path, v))[1] != h
    assert dataset_hash(ds) == h  # stable


def test_hash_ignores_provenance_and_case_order(tmp_path):
    two = YAML + "  - {id: a2, title: B, category: c, description: d, input: x, assertions: [{type: output_contains, value: x}]}\n"
    ds = load_dataset(write(tmp_path, two))
    h = dataset_hash(ds)
    ds.cases.reverse()
    assert dataset_hash(ds) == h
    ds.cases[0].provenance = {"note": "origin"}
    assert dataset_hash(ds) == h


def test_validation_problems(tmp_path):
    bad = YAML.replace("description: why a1 exists", "description: ''")
    with pytest.raises(DatasetError) as e:
        load_and_validate(write(tmp_path, bad))
    assert any("description" in p for p in e.value.problems)
    dup = YAML + "  - {id: a1, title: B, category: c, description: d, input: x, assertions: [{type: nope}]}\n"
    ds = load_dataset(write(tmp_path, dup))
    probs = validate_dataset(ds)
    assert any("duplicate" in p for p in probs) and any("unknown assertion" in p for p in probs)
    assert validate_dataset(Dataset(name="e", version="v", cases=[])) == ["dataset has no cases"]


# --------------------------------------------------------------- runner ---
def case_with(*assertions, **kw):
    return Case(id="k", title="t", category="c", description="d", input="i",
                assertions=[AssertionSpec(**a) for a in assertions], **kw)


def test_status_semantics():
    ok = score_result(case_with({"type": "output_contains", "value": "yes"}), mk(final_output="yes"))
    bad = score_result(case_with({"type": "output_contains", "value": "yes"}), mk(final_output="no"))
    err = score_result(case_with({"type": "output_contains", "value": "yes"}), AgentResult(error="boom"))
    inv = score_result(case_with({"type": "nope"}), mk())
    assert (ok.status, bad.status, err.status, inv.status) == (
        SampleStatus.PASSED, SampleStatus.FAILED, SampleStatus.EXECUTION_ERROR, SampleStatus.INVALID)
    assert err.failure_labels == ["execution_error"] and "incorrect_final_answer" in bad.failure_labels


def test_non_gating_assertion_does_not_fail_case():
    c = case_with({"type": "output_contains", "value": "yes"},
                  {"type": "max_latency_ms", "limit": 1, "gating": False})
    s = score_result(c, mk(final_output="yes", latency_ms=500))
    assert s.status == SampleStatus.PASSED


def test_adapter_exception_is_execution_error_not_failure():
    def boom(case, ctx):
        raise RuntimeError("provider 500")

    ds = Dataset(name="d", version="v", cases=[case_with({"type": "output_contains", "value": "x"})])
    out = execute_run(CallableAdapter("a", "v1", boom), ds, "r1", samples=2)
    assert [s.status for s in out] == [SampleStatus.EXECUTION_ERROR] * 2


def test_execute_run_sample_indexes_and_concurrency():
    seen = []

    def fn(case, ctx: RunContext):
        seen.append(ctx.sample_index)
        return AgentResult(final_output="ok")

    ds = Dataset(name="d", version="v", cases=[case_with({"type": "output_contains", "value": "ok"})])
    out = execute_run(CallableAdapter("a", "v1", fn), ds, "r1", samples=3, concurrency=3)
    assert sorted(s.sample_index for s in out) == [0, 1, 2] and sorted(seen) == [0, 1, 2]


# ------------------------------------------------------------ taxonomy ----
def test_taxonomy_labels():
    c = case_with({"type": "tool_not_called", "name": "issue_refund", "layer": "policy"},
                  {"type": "tool_arguments_match", "name": "upd", "arguments": {"zip": "1"}, "layer": "component"},
                  {"type": "max_latency_ms", "limit": 1, "layer": "outcome"})
    r = mk(calls=[("issue_refund", {}), ("upd", {"zip": "2"})], latency_ms=9, final_output="x")
    s = score_result(c, r)
    assert {"forbidden_tool", "policy_violation", "wrong_tool_arguments", "latency_budget"} <= set(s.failure_labels)
    assert all(label in TAXONOMY for label in s.failure_labels)
    assert classify_failure(SampleStatus.PASSED, s.assertions, r) == []


def test_explicit_label_overrides():
    c = case_with({"type": "output_not_contains", "value": "SECRET", "layer": "policy",
                   "label": "prompt_injection_failure"})
    s = score_result(c, mk(final_output="here SECRET"))
    assert s.failure_labels == ["prompt_injection_failure"]


# ----------------------------------------------------------- trajectory ---
def test_trajectory_checks_and_diff():
    c = case_with({"type": "output_contains", "value": "x"},
                  trajectory={"max_duplicate_calls": 1, "max_consecutive_errors": 1,
                              "require_before": [["lookup", "refund"]]})
    r = mk(calls=[("refund", {"a": 1}), ("refund", {"a": 1}), ("lookup", {})])
    r.tool_calls[0].error = "e"
    r.tool_calls[1].error = "e"
    res = {a.name: a for a in trajectory_checks(c, r)}
    assert not res["no_duplicate_calls"].passed and not res["no_error_thrashing"].passed
    assert not res["lookup_before_refund"].passed
    a = mk(calls=[("lookup", {"id": 1}), ("refund", {"amt": 5})])
    b = mk(calls=[("lookup", {"id": 1}), ("refund", {"amt": 6}), ("notify", {})])
    d = diff_trajectories(a, b)
    assert d["added_tools"] == ["notify"] and d["changed_arguments"][0]["tool"] == "refund"
    assert not d["identical"] and diff_trajectories(a, a)["identical"]


# ----------------------------------------------------------- calibration --
def test_kappa_known_values():
    a = [True, True, False, False]
    assert cohens_kappa(a, a) == 1.0
    assert cohens_kappa(a, [not x for x in a]) == -1.0
    assert cohens_kappa([True] * 4, [True] * 4) == 1.0
    assert cohens_kappa([True] * 4, [True, True, True, False]) == 0.0  # degenerate rater
    # 2x2: po=0.7, pa=pb=0.5 -> pe=.5 -> kappa=.4
    x = [True] * 5 + [False] * 5
    y = [True] * 4 + [False] + [True] * 2 + [False] * 3
    assert cohens_kappa(x, y) == pytest.approx(0.4)
    with pytest.raises(ValueError):
        cohens_kappa([True], [])


def test_confusion_matrix_and_metrics():
    pred = [True, True, True, False, False, False, True, False]
    ref = [True, True, False, False, False, True, False, False]
    m = calibration_metrics(pred, ref)
    assert (m.tp, m.fp, m.tn, m.fn) == (2, 2, 3, 1)
    assert m.accuracy == pytest.approx(5 / 8) and m.precision == pytest.approx(0.5)
    assert m.recall == pytest.approx(2 / 3) and m.fpr == pytest.approx(2 / 5) and m.fnr == pytest.approx(1 / 3)
    assert m.f1 == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))


def test_metrics_edge_cases():
    m = calibration_metrics([], [])
    assert m.n == 0 and m.accuracy == 0.0
    one = calibration_metrics([True] * 5, [True] * 5)  # one class only
    assert one.n_neg == 0 and one.fpr == 0.0
    d = admit(one, AdmissionPolicy(min_items=5, min_per_class=1))
    assert not d.admitted and any("'fail' reference" in r for r in d.reasons)


def test_admission_policy_each_reason():
    good_pred = [True] * 28 + [False] * 2 + [False] * 19 + [True] * 1
    good_ref = [True] * 30 + [False] * 20
    d = admit(calibration_metrics(good_pred, good_ref))
    assert d.admitted and d.label.startswith("CALIBRATED")
    few = admit(calibration_metrics([True, False], [True, False]))
    assert not few.admitted and any("labeled items" in r for r in few.reasons)
    lenient = admit(calibration_metrics([True] * 50, [True] * 30 + [False] * 20))
    assert any("false-positive" in r for r in lenient.reasons) and lenient.label.startswith("NOT CALIBRATED")
    imbalanced = admit(calibration_metrics([True] * 52, [True] * 52))
    assert any("'fail' reference" in r for r in imbalanced.reasons)


def test_judge_identity_changes_with_any_component():
    from evalcore.calibration import judge_identity
    base = judge_identity("litellm", "m1", "p1")
    assert judge_identity("litellm", "m2", "p1") != base and judge_identity("litellm", "m1", "p2") != base
    assert judge_identity("heuristic", "m1", "p1") != base and judge_identity("litellm", "m1", "p1") == base


def test_inter_annotator_agreement_and_adjudication():
    ann = {"a": {"i1": True, "i2": False, "i3": True, "i4": False},
           "b": {"i1": True, "i2": False, "i3": False, "i4": False}}
    k, n = mean_pairwise_kappa(ann)
    assert n == 4 and k == pytest.approx(0.5)
    assert mean_pairwise_kappa({"a": ann["a"]}) == (None, 0)  # no consensus claimed from one annotator
    assert find_disagreements(ann) == {"i3": {"a": True, "b": False}}


# ---------------------------------------------------------------- judge ---
GOOD = json.dumps({"passed": True, "score": 0.9, "label": "pass", "rationale": "ok", "evidence": ["e"]})


def test_parse_verdict_strict():
    assert parse_verdict("```json\n" + GOOD + "\n```").passed
    for bad in ["not json", '{"passed": true}', json.dumps({"passed": True, "score": 2, "label": "pass", "rationale": "r"}),
                json.dumps({"passed": True, "score": .5, "label": "fail", "rationale": "r"}),
                json.dumps({"passed": True, "score": .5, "label": "pass", "rationale": "r", "extra": 1})]:
        with pytest.raises(MalformedJudgeOutput):
            parse_verdict(bad)


def test_judge_retries_malformed_then_succeeds_and_gives_up():
    cfg = JudgeConfig(backend="scripted", model="s", max_retries=2)
    out = Judge(ScriptedBackend(["garbage", "{}", GOOD]), cfg).evaluate("MUST: x", "q", "a")
    assert out.ok and out.attempts == 3
    out = Judge(ScriptedBackend(["x", "y", "z"]), cfg).evaluate("MUST: x", "q", "a")
    assert not out.ok and (out.error or "").startswith("malformed_output")
    out = Judge(ScriptedBackend([RuntimeError("429")]), cfg).evaluate("MUST: x", "q", "a")
    assert not out.ok and (out.error or "").startswith("provider_error")


def test_judge_prompt_hash_tracks_template_and_rubric_version():
    a = JudgeConfig(backend="h", model="m")
    b = JudgeConfig(backend="h", model="m", rubric_version="r2")
    c = JudgeConfig(backend="h", model="m", prompt_template=a.prompt_template + " ")
    assert len({a.prompt_hash, b.prompt_hash, c.prompt_hash}) == 3


def test_heuristic_judge_and_gating_requires_admission():
    case = case_with({"type": "output_contains", "value": "x"},
                     rubric={"judge": {"must": ["refund approved"], "must_not": ["guarantee"]}})
    case.assertions = [AssertionSpec.model_validate({"type": "max_turns", "limit": 9})]
    j = Judge(HeuristicJudge(), JudgeConfig(backend="heuristic", model="keyword-v1"))
    r = mk(final_output="Your refund approved.")
    diag = score_result(case, r, judge=j, judge_admitted=False)
    gated = score_result(case, mk(final_output="nothing relevant"), judge=j, judge_admitted=True)
    ungated = score_result(case, mk(final_output="nothing relevant"), judge=j, judge_admitted=False)
    assert diag.judge and diag.judge["admitted"] is False and gated.status == SampleStatus.FAILED
    assert ungated.status == SampleStatus.PASSED  # uncalibrated judge can NEVER fail a case


def test_judge_failure_is_not_agent_failure():
    case = case_with({"type": "output_contains", "value": "x"}, rubric={"judge": {"must": ["a"]}})
    j = Judge(ScriptedBackend(["bad"] * 3), JudgeConfig(backend="s", model="m"))
    s = score_result(case, mk(final_output="x"), judge=j, judge_admitted=True)
    assert s.judge and s.status == SampleStatus.PASSED and s.judge["error"].startswith("malformed_output")


# ------------------------------------------------- manifest / comparison --
def man(**kw) -> RunManifest:
    base: dict[str, Any] = dict(run_id="r", run_type="synthetic_demo", agent="support", agent_version="v1", dataset_name="d",
                dataset_hash="h1", fixture_hash="f1", case_ids=["a", "b"], samples_per_case=1,
                model="synthetic-sim-small", judge_backend="heuristic", judge_model="k", judge_prompt_hash="p")
    base.update(kw)
    return RunManifest(**base)


def samp(cid, idx, status):
    return SampleResult(case_id=cid, category="c", sample_index=idx, status=status, result=AgentResult())


P, F, E = SampleStatus.PASSED, SampleStatus.FAILED, SampleStatus.EXECUTION_ERROR


def good_set(statuses=(P, P)):
    return [samp(c, 0, s) for c, s in zip("ab", statuses, strict=True)]


def test_manifest_hash_ignores_volatile_but_not_provenance():
    a, b = man(run_id="x"), man(run_id="y", git_commit="zzz")
    assert a.content_hash() == b.content_hash()
    assert man(judge_prompt_hash="other").content_hash() != a.content_hash()


@pytest.mark.parametrize("change,code", [
    ({"dataset_hash": "h2"}, "dataset_mismatch"), ({"fixture_hash": "f2"}, "fixture_mismatch"),
    ({"judge_prompt_hash": "p2"}, "judge_changed"), ({"samples_per_case": 2}, "sample_count_mismatch"),
    ({"case_ids": ["a", "c"]}, "case_set_mismatch"), ({"model": "other"}, "model_mismatch")])
def test_invalid_pairs(change, code):
    rep = validate_pair(man(), man(**change), good_set(), good_set(), "strict")
    assert not rep.valid and any(i.code == code for i in rep.issues)


def test_exploratory_downgrades_provenance_but_not_structure():
    rep = validate_pair(man(), man(judge_prompt_hash="p2"), good_set(), good_set(), "exploratory")
    assert rep.valid and rep.warnings
    rep2 = validate_pair(man(), man(), good_set(), good_set()[:1], "exploratory")
    assert not rep2.valid and any("missing_samples" in r for r in rep2.reasons)


def test_missing_incomplete_duplicate_and_errors():
    assert not validate_pair(man(), man(), good_set(), good_set(), base_complete=False).valid
    dup = good_set() + [samp("a", 0, P)]
    assert any("duplicate_samples" in r for r in validate_pair(man(), man(), good_set(), dup).reasons)
    errs = validate_pair(man(), man(), good_set((E, P)), good_set())
    assert not errs.valid  # 50% execution errors masquerading as data
    small = [samp(c, i, P) for c in "ab" for i in range(10)]
    big_m = man(samples_per_case=10)
    ok = validate_pair(big_m, big_m, small[:19] + [samp("b", 9, E)], small)
    assert ok.valid and ok.warnings


def many(n, rate_fn, k=1):
    out = []
    for i in range(n):
        for j in range(k):
            out.append(samp(f"c{i}", j, P if rate_fn(i, j) else F))
    return out


def test_end_to_end_compare_and_gate():
    ids = [f"c{i}" for i in range(60)]
    bm, cm = man(case_ids=ids), man(case_ids=ids, agent_version="v2")
    pol = BootstrapPolicy(min_cases=50, n_boot=2000, margin=0.05)
    reg = compare_runs(bm, many(60, lambda i, j: True), cm, many(60, lambda i, j: i >= 30), pol)
    assert reg.decision == Decision.SIGNIFICANT_REGRESSION and not gate(reg).passed
    assert len(reg.case_changes) == 30 and "regression" in reg.explanation.lower()
    imp = compare_runs(bm, many(60, lambda i, j: i >= 30), cm, many(60, lambda i, j: True), pol)
    assert imp.decision == Decision.SIGNIFICANT_IMPROVEMENT and gate(imp).passed
    inv = compare_runs(bm, many(60, lambda i, j: True), man(case_ids=ids, dataset_hash="zz"),
                       many(60, lambda i, j: True), pol)
    assert inv.decision == Decision.INVALID and not gate(inv).passed and "INVALID" in inv.explanation
    small_ids = ids[:10]
    inc = compare_runs(man(case_ids=small_ids), many(10, lambda i, j: True), man(case_ids=small_ids),
                       many(10, lambda i, j: True), pol)
    assert inc.decision == Decision.INCONCLUSIVE and not gate(inc, conservative=True).passed
    assert gate(inc, conservative=False).passed
    assert not gate(imp, judge_ok=False).passed  # uncalibrated judge blocks gating


# ------------------------------------------------- redaction / tracing ----
def test_redaction_keys_patterns_known_and_truncation():
    r = Redactor(known_secrets=("hunter2hunter2",), max_text=40)
    out = r.apply({"api_key": "abc", "note": "token sk-abcdefghijklmnopqrstuvwx and hunter2hunter2",
                   "nested": [{"password": "p"}], "long": "z" * 100, "DEMO": "DEMO_SECRET_DO_NOT_REVEAL_7F2A"})
    assert out["api_key"] == REDACTED and out["nested"][0]["password"] == REDACTED
    assert "sk-abc" not in out["note"] and "hunter2" not in out["note"]
    assert out["long"].endswith("chars]") and REDACTED in out["DEMO"]


def test_trace_recorder_tree_timing_and_redaction():
    tr = TraceRecorder(Redactor())
    with tr.span("invoke_agent demo", {"gen_ai.operation.name": "invoke_agent"}):
        tr.advance(10)
        with tr.span("execute_tool lookup", {"gen_ai.operation.name": "execute_tool",
                                             "gen_ai.tool.call.arguments": {"api_key": "x", "id": 1}}):
            tr.advance(25)
        with pytest.raises(ValueError), tr.span("chat m", {"gen_ai.operation.name": "chat"}):
            tr.advance(5)
            raise ValueError("bad")
    recs = {r.name: r for r in tr.records()}
    root, tool, chat = recs["invoke_agent demo"], recs["execute_tool lookup"], recs["chat m"]
    assert tool.parent_id == root.span_id and tool.kind == "tool" and tool.duration_ms == 25
    assert root.duration_ms == 40 and chat.status == "error" and root.kind == "agent"
    assert "[REDACTED]" in tool.attributes["gen_ai.tool.call.arguments"] and "x" not in json.loads(
        tool.attributes["gen_ai.tool.call.arguments"])["api_key"]


# ------------------------------------------------------------- distill ----
def test_distill_marks_candidate_with_provenance():
    src = case_with({"type": "output_contains", "value": "x"})
    res = mk(calls=[("lookup", {"id": 1}), ("done", {})], final_output="all good here")
    d = distill_case(src, res, "run12345", 2, True)
    assert d["provenance"]["status"] == "candidate" and d["id"].startswith("candidate-k-run12345")
    assert any(a["type"] == "tool_sequence" for a in d["assertions"])
    assert "NEEDS HUMAN REVIEW" in d["description"]


def test_tool_call_model_validation():
    with pytest.raises(Exception):
        ToolCall(name="x", bogus=1)  # type: ignore[call-arg]
    assert Layer.POLICY.value == "policy"


def test_pricing_never_invents_prices():
    from evalcore.pricing import SYNTHETIC_PRICES, PriceTable
    assert SYNTHETIC_PRICES.cost("synthetic-sim-small", 1_000_000, 1_000_000) == pytest.approx(2.0)
    assert SYNTHETIC_PRICES.cost("claude-unknown", 10, 10) is None and PriceTable("v").cost(None, 1, 1) is None


def test_simulated_user_scripted_and_llm_modes():
    from evalcore.models import SimulatedUser
    from evalcore.simulation import UserSimulator
    spec = SimulatedUser(persona="confused", max_turns=2, script=["hi", "what?", "never"])
    u = UserSimulator(spec)
    assert [u.next_message([]), u.next_message([]), u.next_message([])] == ["hi", "what?", None]

    class Echo:
        def complete(self, prompt):
            return "llm says hi"

    assert UserSimulator(SimulatedUser(persona="p", max_turns=1), Echo()).next_message([]) == "llm says hi"


def test_litellm_backend_with_injected_completion():
    from types import SimpleNamespace

    from evalcore.judge import LiteLLMBackend

    def fake(**kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=GOOD))])

    out = Judge(LiteLLMBackend("m", completion=fake), JudgeConfig(backend="litellm", model="m")).evaluate("r", "q", "a")
    assert out.ok
