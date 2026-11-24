"""Support operations reference agent (versions pinned in PINS.md)."""

from __future__ import annotations

from pathlib import Path

from .harness import SupportAdapter


def make_adapter(version: str) -> SupportAdapter:
    import importlib

    mod = importlib.import_module(f"demo_agents.support.{version}.agent")
    return SupportAdapter(version, mod, Path(__file__).parent / version)
