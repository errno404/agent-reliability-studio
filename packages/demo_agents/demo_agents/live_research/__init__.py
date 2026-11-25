"""LIVE research agents: a real LLM (via the user's authenticated Claude Code CLI) using ONLY the frozen fixture-web MCP tools.

The model's decisions and answers come from the provider; the environment is the synthetic fixture. Versions are pinned
(see PINS.md). Local/admin execution only: this path spends the user's subscription/API allowance.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from evalcore.adapters import ClaudeCodeToolAgent

from ..runtime import dir_hash

HERE = Path(__file__).parent
FIXTURE_PKG = Path(__file__).resolve().parents[4] / "mcp" / "fixture_web"
TOOLS = ["mcp__fixture__web_search", "mcp__fixture__web_fetch", "mcp__fixture__read_context"]
DEFAULT_MODEL = "haiku"
CORPUS = HERE.resolve().parents[3] / "fixtures" / "web" / "corpus-v2.yaml"


def mcp_servers() -> dict[str, Any]:
    """The frozen fixture web, spawned per run over stdio (read-only, deterministic, no network)."""
    return {
        "fixture": {
            "command": sys.executable,
            "args": ["-m", "fixture_web.server"],
            "env": {"PYTHONPATH": str(FIXTURE_PKG), "FIXTURE_CORPUS": str(CORPUS)},
        }
    }


def versions() -> list[str]:
    return sorted(p.name for p in HERE.iterdir() if p.is_dir() and p.name.startswith("v"))


def make_agent(
    version: str,
    model: str = DEFAULT_MODEL,
    timeout_s: float = 180.0,
    max_budget_usd: float = 0.50,
    binary: str | None = None,
) -> ClaudeCodeToolAgent:
    import hashlib

    vdir = HERE / version
    prompt = (vdir / "PROMPT.md").read_text()
    agent = ClaudeCodeToolAgent(
        "research-live",
        version,
        prompt,
        mcp_servers(),
        TOOLS,
        model=model,
        timeout_s=timeout_s,
        max_budget_usd=max_budget_usd,
        binary=binary,
    )
    agent.agent_hash = dir_hash(vdir)  # type: ignore[attr-defined]
    agent.prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]  # type: ignore[attr-defined]
    agent.requested_model = model  # type: ignore[attr-defined]
    return agent
