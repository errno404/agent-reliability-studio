"""Framework-agnostic agent registry: ONE place that turns a spec string into an adapter + honest identity.

Specs
  ``support:v2`` | ``research:v1`` | ``coding:v2`` | ``redteam:v1``      scripted, seeded SYNTHETIC agents
  ``live:research:v1?model=haiku&timeout=180&budget=0.5``                a REAL LLM (Claude Code CLI + fixture MCP tools)

Both kinds are consumed by the same runner, tracing, persistence, statistics and dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

from evalcore.hashing import hash_obj
from evalcore.pricing import SYNTHETIC_PRICES, PriceTable


class UnknownAgent(KeyError):
    pass


@dataclass(frozen=True)
class ResolvedAgent:
    spec: str
    adapter: Any
    agent: str  # catalog agent name (e.g. "support", "research-live")
    version: str
    execution_kind: str  # "synthetic" | "live"
    provider: str
    model: str  # requested model (alias for live agents)
    agent_hash: str
    prompt_hash: str
    tool_schema_hash: str
    config: dict[str, Any] = field(default_factory=dict)  # sanitized, behaviour-affecting settings (no secrets)
    price_table: PriceTable | None = None


def parse(spec: str) -> tuple[str, str, str, dict[str, str]]:
    """-> (kind, agent, version, options)"""
    base, _, query = spec.partition("?")
    parts = base.split(":")
    kind = "synthetic"
    if parts[0] == "live":
        kind, parts = "live", parts[1:]
    if len(parts) != 2:
        raise UnknownAgent(f"bad agent spec '{spec}' (expected agent:version or live:agent:version)")
    return kind, parts[0], parts[1], dict(parse_qsl(query))


# Live execution spends the operator's own CLI quota: operator-only (the API gates it by admin auth + DEMO_MODE), and every
# per-run knob is clamped server-side so a spec string cannot raise limits or select arbitrary models.
ALLOWED_LIVE_MODELS = frozenset({"haiku", "sonnet"})
MAX_BUDGET_USD = 2.0
MAX_TIMEOUT_S = 300.0


def _clamp(raw: object, lo: float, hi: float, name: str) -> float:
    try:
        v = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise UnknownAgent(f"{name} must be a number") from None
    if not lo <= v <= hi:
        raise UnknownAgent(f"{name} must be between {lo} and {hi}")
    return v


def resolve(spec: str) -> ResolvedAgent:
    kind, agent, version, opts = parse(spec)
    if kind == "live":
        from demo_agents import live_research

        if agent != "research" or version not in live_research.versions():
            raise UnknownAgent(
                f"unknown live agent '{spec}'. available: "
                + ", ".join(f"live:research:{v}" for v in live_research.versions())
            )
        model = opts.get("model", live_research.DEFAULT_MODEL)
        if model not in ALLOWED_LIVE_MODELS:
            raise UnknownAgent(f"model '{model}' is not allowed; allowed: {sorted(ALLOWED_LIVE_MODELS)}")
        timeout_s = _clamp(opts.get("timeout", 180), 1, MAX_TIMEOUT_S, "timeout")
        budget = _clamp(opts.get("budget", 0.50), 0.01, MAX_BUDGET_USD, "budget")
        ad = live_research.make_agent(version, model=model, timeout_s=timeout_s, max_budget_usd=budget)
        cfg = {
            "harness": "claude-code-cli",
            "model_requested": model,
            "tools": live_research.TOOLS,
            "isolation": "strict-mcp,no-builtin-tools,no-settings",
            "per_run_budget_usd": budget,
            "timeout_s": timeout_s,
        }
        return ResolvedAgent(
            spec,
            ad,
            "research-live",
            version,
            "live",
            "anthropic",
            model,
            ad.agent_hash,
            ad.prompt_hash,  # type: ignore[attr-defined]
            hash_obj(sorted(live_research.TOOLS), 16),
            cfg,
            None,
        )
    from demo_agents import VERSIONS, agent_info, get_adapter

    if agent not in VERSIONS or version not in VERSIONS[agent]:
        raise UnknownAgent(f"unknown agent '{spec}'")
    info = agent_info(f"{agent}:{version}")
    return ResolvedAgent(
        spec,
        get_adapter(f"{agent}:{version}"),
        info["agent"],
        info["version"],
        "synthetic",
        "synthetic",
        info["model"],
        info["agent_hash"],
        info["prompt_hash"],
        info["tool_schema_hash"],
        {"scripted": True, "seeded_fault_injection": True},
        SYNTHETIC_PRICES,
    )
