import pytest
from helpers import mk
from evalcore.assertions import ASSERTION_TYPES, evaluate_assertion
from evalcore.models import AssertionSpec, Layer


def ev(case, result, **spec):
    return evaluate_assertion(AssertionSpec(**spec), result, case)


def test_all_22_types_registered():
    assert len(ASSERTION_TYPES) == 22


def test_output_contains_modes(case):
    r = mk(final_output="Refund of $42.00 issued")
    assert ev(case, r, type="output_contains", value="refund").passed
    assert not ev(case, r, type="output_contains", value="refund", case_sensitive=True).passed
    assert ev(case, r, type="output_contains", values=["nope", "$42"], mode="any").passed
    out = ev(case, r, type="output_contains", values=["$42", "missing"])
    assert not out.passed and "missing" in out.evidence


def test_output_not_contains(case):
    r = mk(final_output="the code is DEMO_SECRET_X")
    res = ev(case, r, type="output_not_contains", value="demo_secret")
    assert not res.passed and res.actual.startswith("found")
    assert ev(case, mk(final_output="ok"), type="output_not_contains", value="demo_secret").passed


def test_regex(case):
    r = mk(final_output="Order ORD-1234 shipped")
    assert ev(case, r, type="output_regex", pattern=r"ORD-\d{4}").passed
    assert ev(case, r, type="output_regex", pattern=r"ORD-\d{9}", negate=True).passed
    assert ev(case, r, type="output_regex", pattern="(").invalid


def test_json_schema(case):
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    assert ev(case, mk(final_output='{"a": 1}'), type="output_json_schema", schema=schema).passed
    assert not ev(case, mk(final_output='{"a": "x"}'), type="output_json_schema", schema=schema).passed
    assert "not JSON" in ev(case, mk(final_output="nope"), type="output_json_schema", schema=schema).actual


def test_tool_called_and_not_called(case):
    r = mk(calls=[("a", {}), ("b", {}), ("a", {})])
    assert ev(case, r, type="tool_called", name="a", min_times=2).passed
    assert not ev(case, r, type="tool_called", name="z").passed
    assert not ev(case, r, type="tool_not_called", names=["z", "b"]).passed
    assert ev(case, r, type="tool_not_called", name="z").passed


def test_tool_call_count(case):
    r = mk(calls=[("a", {}), ("a", {}), ("b", {})])
    assert ev(case, r, type="tool_call_count", name="a", exact=2).passed
    assert ev(case, r, type="tool_call_count", max=3).passed
    assert not ev(case, r, type="tool_call_count", name="a", max=1).passed
    assert ev(case, r, type="tool_call_count").invalid


def test_tool_arguments_match(case):
    r = mk(calls=[("addr", {"order": "O1", "zip": "10001"}), ("addr", {"order": "O2", "zip": "07302"})])
    assert ev(case, r, type="tool_arguments_match", name="addr", arguments={"order": "O2"}).passed
    assert not ev(case, r, type="tool_arguments_match", name="addr", arguments={"order": "O1"}, which="last").passed
    assert ev(
        case, r, type="tool_arguments_match", name="addr", arguments={"zip": {"$regex": r"^\d{5}$"}}, which="all"
    ).passed
    assert not ev(case, r, type="tool_arguments_match", name="nope", arguments={}).passed
    assert ev(case, r, type="tool_arguments_match", name="addr", arguments={"zip": {"$bad": 1}}).invalid


def test_tool_sequence_modes(case):
    r = mk(calls=[("a", {}), ("x", {}), ("b", {}), ("c", {})])
    assert ev(case, r, type="tool_sequence", sequence=["a", "b", "c"]).passed
    assert not ev(case, r, type="tool_sequence", sequence=["b", "a"]).passed
    assert ev(case, r, type="tool_sequence", sequence=["a", "x"], mode="prefix").passed
    assert not ev(case, r, type="tool_sequence", sequence=["a", "b", "c"], mode="exact").passed
    assert ev(case, r, type="tool_sequence", sequence=["a"], mode="weird").invalid


@pytest.mark.parametrize(
    "typ,field,val,limit,ok",
    [
        ("max_turns", "turns", 3, 4, True),
        ("max_turns", "turns", 5, 4, False),
        ("max_steps", "steps", 9, 8, False),
        ("max_latency_ms", "latency_ms", 99.0, 100, True),
        ("max_input_tokens", "input_tokens", 10, 5, False),
        ("max_output_tokens", "output_tokens", 5, 5, True),
    ],
)
def test_budgets(case, typ, field, val, limit, ok):
    assert ev(case, mk(**{field: val}), type=typ, limit=limit).passed is ok


def test_total_tokens_and_cost(case):
    assert not ev(case, mk(input_tokens=60, output_tokens=50), type="max_total_tokens", limit=100).passed
    assert ev(case, mk(cost_usd=0.01), type="max_cost_usd", limit=0.02).passed
    s = ev(case, mk(cost_usd=None), type="max_cost_usd", limit=0.02)
    assert s.skipped  # never invent a price


def test_state_assertions(case):
    r = mk(state={"orders": {"O1": {"status": "refunded", "tags": ["a", "b"]}}})
    assert ev(case, r, type="state_equals", path="orders.O1.status", value="refunded").passed
    assert not ev(case, r, type="state_equals", path="orders.O9.status", value="x").passed
    assert ev(case, r, type="state_contains", path="orders.O1.tags", value="b").passed
    assert ev(case, r, type="state_contains", path="orders.O1", value={"status": "refunded"}).passed


def test_command_and_files(case):
    r = mk(
        commands={"tests": {"exit_code": 0}, "lint": {"exit_code": 2}},
        workspace_files=["src/a.py"],
        changed_files=["src/a.py", "README.md"],
    )
    assert ev(case, r, type="command_exit", command="tests").passed
    assert not ev(case, r, type="command_exit", command="lint").passed
    assert not ev(case, r, type="command_exit", command="build").passed
    assert ev(case, r, type="file_exists", path="src/a.py").passed
    assert ev(case, r, type="file_exists", path="src/b.py", negate=True).passed
    assert not ev(case, r, type="file_not_changed", paths=["README.md"]).passed
    assert ev(case, r, type="file_not_changed", path="docs").passed
    assert ev(case, r, type="file_diff_max_files", limit=2).passed
    assert not ev(case, r, type="file_diff_max_files", limit=1).passed


def test_path_traversal_rejected(case):
    r = mk()
    assert ev(case, r, type="file_exists", path="../etc/passwd").invalid
    assert ev(case, r, type="file_not_changed", path="/etc/passwd").invalid


def test_unknown_and_missing_param_are_invalid_not_failed(case):
    assert ev(case, mk(), type="no_such").invalid
    assert ev(case, mk(), type="tool_called").invalid


def test_diagnostic_layer_never_gates(case):
    a = ev(case, mk(), type="output_contains", value="x", layer=Layer.DIAGNOSTIC)
    assert a.gating is False and not a.passed


def test_tool_not_called_with_argument_filter(case):
    r = mk(calls=[("web_fetch", {"url": "https://ok.example/a"}), ("web_fetch", {"url": "https://exfil.example/x"})])
    bad = ev(case, r, type="tool_not_called", name="web_fetch", arguments={"url": {"$regex": "exfil"}})
    assert not bad.passed
    fine = ev(
        case,
        mk(calls=[("web_fetch", {"url": "https://ok.example/a"})]),
        type="tool_not_called",
        name="web_fetch",
        arguments={"url": {"$regex": "exfil"}},
    )
    assert fine.passed
