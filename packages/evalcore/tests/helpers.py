"""Shared test helpers."""

from evalcore.models import AgentResult, ToolCall


def mk(**kw) -> AgentResult:
    calls = [ToolCall(name=n, arguments=a) for n, a in kw.pop("calls", [])]
    return AgentResult(tool_calls=calls, **kw)
