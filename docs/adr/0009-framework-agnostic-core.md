# 0009 — `evalcore` is framework-agnostic
**Status:** accepted
**Decision:** The core imports no web framework or ORM and talks to systems through an `AgentAdapter` protocol (callable, LangGraph message parsing, Claude Code CLI, LiteLLM). API, CLI and worker share a service layer.
**Consequences:** Reusable in notebooks/CI; testable in isolation (≈96% coverage).
