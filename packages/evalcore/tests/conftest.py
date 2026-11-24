import pytest
from evalcore.models import AgentResult, Case, ToolCall


@pytest.fixture
def case() -> Case:
    return Case(id="c1", title="t", category="x", description="d", input="hi")


def mk(**kw) -> AgentResult:
    calls = [ToolCall(name=n, arguments=a) if isinstance(n, str) else n for n, a in kw.pop("calls", [])]
    return AgentResult(tool_calls=calls, **kw)
