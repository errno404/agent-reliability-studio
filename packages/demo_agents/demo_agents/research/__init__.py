"""Research reference agent over the frozen MCP fixture web (v1 plain Python, v2 LangGraph)."""

from __future__ import annotations

import importlib
from pathlib import Path

from .common import ResearchAdapter


def make_adapter(version: str) -> ResearchAdapter:
    mod = importlib.import_module(f"demo_agents.research.{version}.agent")
    return ResearchAdapter(version, mod, Path(__file__).parent / version)
