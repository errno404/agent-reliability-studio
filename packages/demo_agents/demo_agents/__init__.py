"""Deterministic reference systems under test: support, research, coding (+ redteam dispatcher).

``get_adapter("support:v1")`` returns an :class:`evalcore.AgentAdapter`. All behaviour is scripted +
seeded fault injection (NOT LLM output); evaluation machinery around it is real.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evalcore.models import AgentResult, Case
from evalcore.runner import RunContext

from . import coding, research, support

AGENT_DIR = Path(__file__).parent
VERSIONS = {"support": ("v1", "v2"), "research": ("v1", "v2"), "coding": ("v1", "v2"), "redteam": ("v1", "v2")}


class RedteamAdapter:
    """Routes each red-team case to the support or research agent of the same version."""

    name = "redteam"

    def __init__(self, version: str):
        self.version = version
        self.support, self.research = support.make_adapter(version), research.make_adapter(version)
        self.model = self.support.model
        self.agent_hash = f"{self.support.agent_hash}+{self.research.agent_hash}"
        self.prompt_hash = f"{self.support.prompt_hash}+{self.research.prompt_hash}"

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        target = (case.fixture or {}).get("target", "support")
        return (self.research if target == "research" else self.support).run(case, ctx)


def get_adapter(spec: str) -> Any:
    agent, _, version = spec.partition(":")
    if agent not in VERSIONS or version not in VERSIONS[agent]:
        raise KeyError(f"unknown agent '{spec}'. available: " + ", ".join(f"{a}:{v}" for a, vs in VERSIONS.items() for v in vs))
    if agent == "support":
        return support.make_adapter(version)
    if agent == "research":
        return research.make_adapter(version)
    if agent == "coding":
        return coding.make_adapter(version)
    return RedteamAdapter(version)


def agent_info(spec: str) -> dict[str, str]:
    """Pinned identity (hashes) for the manifest/dashboard."""
    ad = get_adapter(spec)
    return {"agent": ad.name, "version": ad.version, "agent_hash": ad.agent_hash, "prompt_hash": ad.prompt_hash,
            "model": ad.model}
