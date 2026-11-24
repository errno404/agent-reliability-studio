"""Frozen synthetic web served over MCP (deterministic, read-only, idempotent)."""

from .corpus import FixtureWeb, load_corpus
from .server import build_server

__all__ = ["FixtureWeb", "build_server", "load_corpus"]
