"""Deterministic assertion engine (22 built-in assertion types).

Every assertion returns an :class:`AssertionResult` carrying expected/actual/evidence.
A malformed spec yields ``invalid=True`` (never a silent pass or a quality failure).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import jsonschema

from .models import AgentResult, AssertionResult, AssertionSpec, Case, Layer

Evaluator = Callable[[dict[str, Any], AgentResult, Case], "Outcome"]


class Outcome:
    """Intermediate result of one evaluator."""

    def __init__(self, passed: bool, expected: Any = None, actual: Any = None, evidence: str = "",
                 skipped: bool = False):
        self.passed, self.expected, self.actual = passed, expected, actual
        self.evidence, self.skipped = evidence, skipped


class BadSpec(ValueError):
    pass


def _need(p: dict[str, Any], key: str) -> Any:
    if key not in p:
        raise BadSpec(f"missing required parameter '{key}'")
    return p[key]


def _safe_rel_path(path: str) -> str:
    """Reject absolute paths and traversal in workspace-relative assertion paths."""
    if path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/") or "\x00" in path:
        raise BadSpec(f"unsafe path '{path}'")
    return path


def _values(p: dict[str, Any]) -> list[str]:
    if "values" in p:
        return [str(v) for v in p["values"]]
    return [str(_need(p, "value"))]


# ---------------------------------------------------------------- output ----
def _contains(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    cs = bool(p.get("case_sensitive", False))
    text = r.final_output if cs else r.final_output.lower()
    vals = _values(p)
    missing = [v for v in vals if (v if cs else v.lower()) not in text]
    mode_any = p.get("mode", "all") == "any"
    ok = (len(missing) < len(vals)) if mode_any else not missing
    return Outcome(ok, vals, f"missing={missing}" if missing else "all present",
                   f"output {'is missing' if missing else 'contains'} {missing or vals}")


def _not_contains(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    cs = bool(p.get("case_sensitive", False))
    text = r.final_output if cs else r.final_output.lower()
    vals = _values(p)
    found = [v for v in vals if (v if cs else v.lower()) in text]
    return Outcome(not found, f"none of {vals}", f"found={found}" if found else "absent",
                   f"forbidden text present: {found}" if found else "no forbidden text present")


def _regex(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    pat = str(_need(p, "pattern"))
    flags = re.IGNORECASE if not p.get("case_sensitive", False) else 0
    try:
        m = re.search(pat, r.final_output, flags | re.MULTILINE)
    except re.error as exc:
        raise BadSpec(f"bad regex: {exc}") from exc
    want = not p.get("negate", False)
    return Outcome(bool(m) == want, pat, m.group(0) if m else None,
                   f"regex {'matched' if m else 'did not match'}")


def _json_schema(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    schema = _need(p, "schema")
    try:
        doc = json.loads(r.final_output)
    except json.JSONDecodeError as exc:
        return Outcome(False, "valid JSON", "not JSON", f"output is not JSON: {exc.msg}")
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        return Outcome(False, "schema-valid", exc.message, f"schema violation at {list(exc.path)}")
    except jsonschema.SchemaError as exc:
        raise BadSpec(f"invalid schema: {exc.message}") from exc
    return Outcome(True, "schema-valid", "schema-valid", "output validates against schema")


# ------------------------------------------------------------------ tools ---
def _calls(r: AgentResult, name: str | None) -> list[Any]:
    return [t for t in r.tool_calls if name is None or t.name == name]


def _tool_called(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    name, mn = str(_need(p, "name")), int(p.get("min_times", 1))
    n = len(_calls(r, name))
    return Outcome(n >= mn, f">= {mn} call(s) to {name}", n, f"{name} called {n}x")


def _tool_not_called(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    names = [str(n) for n in p["names"]] if "names" in p else [str(_need(p, "name"))]
    hit = [n for n in names if _calls(r, n)]
    return Outcome(not hit, f"none of {names}", hit,
                   f"forbidden tool(s) called: {hit}" if hit else "no forbidden tools called")


def _tool_call_count(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    name = p.get("name")
    n = len(_calls(r, name))
    lo, hi = p.get("min"), p.get("max")
    if "exact" in p:
        lo = hi = p["exact"]
    if lo is None and hi is None:
        raise BadSpec("need one of min/max/exact")
    ok = (lo is None or n >= lo) and (hi is None or n <= hi)
    return Outcome(ok, {"min": lo, "max": hi}, n, f"{name or 'all tools'} called {n}x")


def _match_value(want: Any, got: Any) -> bool:
    if isinstance(want, dict) and len(want) == 1 and next(iter(want)).startswith("$"):
        op, arg = next(iter(want.items()))
        if op == "$regex":
            return isinstance(got, str) and re.search(arg, got) is not None
        if op == "$in":
            return got in arg
        if op == "$gte":
            return isinstance(got, (int, float)) and got >= arg
        if op == "$lte":
            return isinstance(got, (int, float)) and got <= arg
        if op == "$exists":
            return (got is not None) == bool(arg)
        raise BadSpec(f"unknown matcher {op}")
    if isinstance(want, dict) and isinstance(got, dict):
        return all(k in got and _match_value(v, got[k]) for k, v in want.items())
    return bool(want == got)


def _tool_args(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    name, want = str(_need(p, "name")), _need(p, "arguments")
    which = p.get("which", "any")  # any | last | first | all
    calls = _calls(r, name)
    if not calls:
        return Outcome(False, want, None, f"{name} was never called")
    results = [_match_value(want, t.arguments) for t in calls]
    table = {"any": any(results), "all": all(results), "last": results[-1], "first": results[0]}
    ok = table.get(which)
    if ok is None:
        raise BadSpec(f"bad 'which': {which}")
    shown = calls[-1].arguments if which == "last" else [t.arguments for t in calls]
    return Outcome(bool(ok), want, shown, f"argument match ({which}) = {ok} over {len(calls)} call(s)")


def _tool_sequence(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    want = [str(x) for x in _need(p, "sequence")]
    mode = p.get("mode", "subsequence")
    got = r.tool_names
    if mode == "exact":
        ok = got == want
    elif mode == "prefix":
        ok = got[: len(want)] == want
    elif mode == "subsequence":
        it = iter(got)
        ok = all(any(g == w for g in it) for w in want)
    else:
        raise BadSpec(f"bad mode {mode}")
    return Outcome(ok, want, got, f"sequence {mode} {'satisfied' if ok else 'violated'}")


# ---------------------------------------------------------------- budgets ---
def _budget(attr: str, label: str) -> Evaluator:
    def ev(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
        limit = _need(p, "limit")
        val = getattr(r, attr)
        return Outcome(val <= limit, f"<= {limit}", val, f"{label} {val} vs limit {limit}")
    return ev


def _max_cost(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    limit = float(_need(p, "limit"))
    if r.cost_usd is None:
        return Outcome(True, f"<= {limit}", None, "no price available; cost not evaluated", skipped=True)
    return Outcome(r.cost_usd <= limit, f"<= {limit}", r.cost_usd, f"cost {r.cost_usd} vs {limit}")


def _max_tokens(attr: str) -> Evaluator:
    def ev(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
        limit = int(_need(p, "limit"))
        val = getattr(r, attr)
        return Outcome(val <= limit, f"<= {limit}", val, f"{attr} {val} vs limit {limit}")
    return ev


# ------------------------------------------------------------------ state ---
def _dig(obj: Any, path: str) -> tuple[bool, Any]:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False, None
    return True, cur


def _state_equals(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    path, want = str(_need(p, "path")), _need(p, "value")
    found, got = _dig(r.state, path)
    return Outcome(found and got == want, want, got if found else "<missing>",
                   f"state[{path}] {'==' if found and got == want else '!='} expected")


def _state_contains(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    path, want = str(_need(p, "path")), _need(p, "value")
    found, got = _dig(r.state, path)
    ok = False
    if found:
        if isinstance(got, (list, tuple, str)):
            ok = want in got
        elif isinstance(got, dict):
            ok = want in got if not isinstance(want, dict) else _match_value(want, got)
    return Outcome(ok, f"contains {want!r}", got if found else "<missing>",
                   f"state[{path}] {'contains' if ok else 'does not contain'} {want!r}")


# ----------------------------------------------------------------- coding ---
def _command_exit(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    name, want = str(_need(p, "command")), int(p.get("code", 0))
    cmd = r.commands.get(name)
    if cmd is None:
        return Outcome(False, want, None, f"command '{name}' was not run")
    got = cmd.get("exit_code")
    return Outcome(got == want, want, got, f"command '{name}' exited {got}")


def _file_exists(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    path = _safe_rel_path(str(_need(p, "path")))
    ok = path in r.workspace_files
    return Outcome(ok == (not p.get("negate", False)), path, ok, f"{path} {'exists' if ok else 'missing'}")


def _file_not_changed(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    paths = [_safe_rel_path(str(x)) for x in (p["paths"] if "paths" in p else [_need(p, "path")])]
    touched = [x for x in r.changed_files if any(x == q or x.startswith(q.rstrip("/") + "/") for q in paths)]
    return Outcome(not touched, f"unchanged: {paths}", touched,
                   f"forbidden files changed: {touched}" if touched else "protected files unchanged")


def _diff_max_files(p: dict[str, Any], r: AgentResult, c: Case) -> Outcome:
    limit = int(_need(p, "limit"))
    n = len(r.changed_files)
    return Outcome(n <= limit, f"<= {limit} files", r.changed_files, f"{n} file(s) changed")


REGISTRY: dict[str, Evaluator] = {
    "output_contains": _contains,
    "output_not_contains": _not_contains,
    "output_regex": _regex,
    "output_json_schema": _json_schema,
    "tool_called": _tool_called,
    "tool_not_called": _tool_not_called,
    "tool_call_count": _tool_call_count,
    "tool_arguments_match": _tool_args,
    "tool_sequence": _tool_sequence,
    "max_turns": _budget("turns", "turns"),
    "max_steps": _budget("steps", "steps"),
    "max_latency_ms": _budget("latency_ms", "latency_ms"),
    "max_input_tokens": _max_tokens("input_tokens"),
    "max_output_tokens": _max_tokens("output_tokens"),
    "max_total_tokens": _max_tokens("total_tokens"),
    "max_cost_usd": _max_cost,
    "state_equals": _state_equals,
    "state_contains": _state_contains,
    "command_exit": _command_exit,
    "file_exists": _file_exists,
    "file_not_changed": _file_not_changed,
    "file_diff_max_files": _diff_max_files,
}
ASSERTION_TYPES = frozenset(REGISTRY)


def evaluate_assertion(spec: AssertionSpec, result: AgentResult, case: Case, idx: int = 0) -> AssertionResult:
    gating = spec.gating and spec.layer != Layer.DIAGNOSTIC
    base = {"name": f"{spec.type}#{idx}", "type": spec.type, "layer": spec.layer, "gating": gating,
            "severity": spec.severity, "label": spec.label}
    ev = REGISTRY.get(spec.type)
    if ev is None:
        return AssertionResult(**base, passed=False, invalid=True, evidence=f"unknown assertion type '{spec.type}'")
    try:
        out = ev(spec.params, result, case)
    except BadSpec as exc:
        return AssertionResult(**base, passed=False, invalid=True, evidence=f"invalid spec: {exc}")
    return AssertionResult(**base, passed=out.passed, expected=out.expected, actual=out.actual,
                           evidence=out.evidence, skipped=out.skipped)


def evaluate_all(case: Case, result: AgentResult) -> list[AssertionResult]:
    return [evaluate_assertion(s, result, case, i) for i, s in enumerate(case.assertions)]


# Layers that are diagnostic-only by default unless explicitly marked gating.
DIAGNOSTIC_LAYERS = frozenset({Layer.DIAGNOSTIC})
