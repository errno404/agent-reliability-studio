"""Trajectory analysis (Layer B) and trajectory diffing."""

from __future__ import annotations

import difflib
import json
from typing import Any

from .models import AgentResult, AssertionResult, Case, Layer, Severity


def _sig(name: str, args: dict[str, Any]) -> str:
    return name + json.dumps(args, sort_keys=True, default=str)


def trajectory_checks(case: Case, r: AgentResult) -> list[AssertionResult]:
    """Generic path-quality checks driven by ``case.trajectory`` (all gating unless 'gating: false').

    keys: max_duplicate_calls, max_consecutive_errors, max_steps (alias), require_before:[[a,b]]
    ``require_before`` = tool ``a`` must appear before first ``b`` (context retrieved before dependent action).
    """
    cfg = case.trajectory
    if not cfg:
        return []
    gating = bool(cfg.get("gating", True))
    out: list[AssertionResult] = []

    def add(name: str, ok: bool, expected: Any, actual: Any, evidence: str, label: str) -> None:
        out.append(
            AssertionResult(
                name=name,
                type=name,
                layer=Layer.TRAJECTORY,
                gating=gating,
                passed=ok,
                expected=expected,
                actual=actual,
                evidence=evidence,
                severity=Severity.MEDIUM,
                label=label,
            )
        )

    if "max_duplicate_calls" in cfg:
        counts: dict[str, int] = {}
        for t in r.tool_calls:
            counts[_sig(t.name, t.arguments)] = counts.get(_sig(t.name, t.arguments), 0) + 1
        worst = max(counts.values(), default=0)
        dups = {k.split("{")[0]: v for k, v in counts.items() if v > cfg["max_duplicate_calls"]}
        limit = cfg["max_duplicate_calls"]
        add(
            "no_duplicate_calls",
            worst <= limit,
            f"<= {limit} identical calls",
            dups or worst,
            f"identical calls repeated: {dups}" if dups else "no repeated identical calls",
            "repeated_tool_loop",
        )
    if "max_consecutive_errors" in cfg:
        run = best = 0
        for t in r.tool_calls:
            run = run + 1 if t.error else 0
            best = max(best, run)
        add(
            "no_error_thrashing",
            best <= cfg["max_consecutive_errors"],
            f"<= {cfg['max_consecutive_errors']} consecutive tool errors",
            best,
            f"longest streak of failing tool calls = {best}",
            "error_thrashing",
        )
    for a, b in cfg.get("require_before", []):
        names = r.tool_names
        ok = (b not in names) or (a in names and names.index(a) < names.index(b))
        add(
            f"{a}_before_{b}",
            ok,
            f"{a} before {b}",
            names,
            f"{a} {'precedes' if ok else 'does not precede'} {b}",
            "wrong_tool_order",
        )
    return out


def trajectory_text(r: AgentResult) -> str:
    return " → ".join(r.tool_names) if r.tool_calls else "(no tool calls)"


def diff_trajectories(base: AgentResult, cand: AgentResult) -> dict[str, Any]:
    """Aligned diff of two tool trajectories: added/removed tools and changed arguments."""
    bn, cn = base.tool_names, cand.tool_names
    sm = difflib.SequenceMatcher(a=bn, b=cn, autojunk=False)
    ops: list[dict[str, Any]] = []
    changed_args: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for off in range(i2 - i1):
                b, c = base.tool_calls[i1 + off], cand.tool_calls[j1 + off]
                if b.arguments != c.arguments:
                    changed_args.append({"tool": b.name, "baseline": b.arguments, "candidate": c.arguments})
                ops.append({"op": "equal", "tool": b.name})
        else:
            ops.append({"op": tag, "baseline": bn[i1:i2], "candidate": cn[j1:j2]})
    return {
        "baseline": bn,
        "candidate": cn,
        "ops": ops,
        "changed_arguments": changed_args,
        "identical": bn == cn and not changed_args,
        "removed_tools": sorted(set(bn) - set(cn)),
        "added_tools": sorted(set(cn) - set(bn)),
        "latency_delta_ms": cand.latency_ms - base.latency_ms,
        "token_delta": cand.total_tokens - base.total_tokens,
        "cost_delta": (cand.cost_usd - base.cost_usd)
        if cand.cost_usd is not None and base.cost_usd is not None
        else None,
    }
