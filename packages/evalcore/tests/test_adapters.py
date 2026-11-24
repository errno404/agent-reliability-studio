import json
import os
import stat
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from evalcore.adapters import (
    ClaudeCodeAdapter,
    LiteLLMAdapter,
    changed_files,
    result_from_langgraph_messages,
    run_command,
    snapshot,
)
from evalcore.models import Case
from evalcore.runner import RunContext

CTX = RunContext(run_id="r", sample_index=0, seed=1)
CASE = Case(id="c", title="t", category="x", description="d", input="fix it")


def fake_cli(tmp_path: Path, body: str) -> str:
    p = tmp_path / "claude"
    p.write_text(f"#!{sys.executable}\nimport sys, json\n{body}\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_claude_adapter_parses_structured_output(tmp_path):
    payload = {
        "result": "done",
        "num_turns": 3,
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "modelUsage": {"claude-x": {}},
        "total_cost_usd": 0.42,
        "session_id": "s",
        "is_error": False,
    }
    ad = ClaudeCodeAdapter(binary=fake_cli(tmp_path, f"print(json.dumps({payload!r}))"))
    r = ad.run(CASE, CTX)
    assert r.error is None and r.final_output == "done" and r.turns == 3 and r.model == "claude-x"
    assert r.cost_usd is None and r.metadata["api_equivalent_cost_usd"] == 0.42  # never claimed as money paid
    assert "API-equivalent" in r.metadata["cost_note"]


def test_claude_adapter_error_modes(tmp_path):
    assert ClaudeCodeAdapter(binary=str(tmp_path / "nope")).run(CASE, CTX).error_kind == "adapter"
    bad = ClaudeCodeAdapter(binary=fake_cli(tmp_path, "print('not json')")).run(CASE, CTX)
    assert bad.error and bad.error_kind == "adapter"
    iserr = ClaudeCodeAdapter(
        binary=fake_cli(tmp_path, "print(json.dumps({'is_error': True, 'result': 'rate limit'}))")
    )
    assert iserr.run(CASE, CTX).error_kind == "provider"


def test_claude_adapter_timeout_kills_process_tree(tmp_path):
    marker = tmp_path / "child_alive"
    body = (
        f"import subprocess, time\nsubprocess.Popen([sys.executable, '-c', \"import time,pathlib;"
        f"time.sleep(1.5);pathlib.Path(r'{marker}').write_text('x')\"])\ntime.sleep(30)"
    )
    ad = ClaudeCodeAdapter(binary=fake_cli(tmp_path, body), timeout_s=0.6)
    r = ad.run(CASE, CTX)
    assert r.error_kind == "timeout"
    time.sleep(2)
    assert not marker.exists()  # grandchild was killed with the group


def test_run_command_no_shell_and_exit_codes(tmp_path):
    code, out, _, to = run_command([sys.executable, "-c", "print('hi'); raise SystemExit(3)"], tmp_path, 5)
    assert (code, out.strip(), to) == (3, "hi", False)
    code, *_ = run_command(["echo", "$HOME;ls"], tmp_path, 5)
    assert code == 0


def test_snapshot_changed_files(tmp_path):
    (tmp_path / "a.txt").write_text("1")
    (tmp_path / "b.txt").write_text("1")
    before = snapshot(tmp_path)
    (tmp_path / "a.txt").write_text("2")
    (tmp_path / "c.txt").write_text("1")
    (tmp_path / "b.txt").unlink()
    assert changed_files(before, snapshot(tmp_path)) == ["a.txt", "b.txt", "c.txt"]


def _resp(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg)], usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3)
    )


def test_litellm_adapter_tool_loop_and_provider_error():
    tc = SimpleNamespace(id="1", function=SimpleNamespace(name="add", arguments=json.dumps({"a": 1, "b": 2})))
    replies = [_resp(tool_calls=[tc]), _resp(content="3")]
    ad = LiteLLMAdapter("a", "v", "m", "sys", {"add": lambda a, b: a + b}, [], completion=lambda **kw: replies.pop(0))
    r = ad.run(CASE, CTX)
    assert r.final_output == "3" and r.tool_calls[0].result == 3 and r.input_tokens == 14 and r.steps == 2

    def boom(**kw):
        raise TimeoutError("slow")

    r2 = LiteLLMAdapter("a", "v", "m", "s", {}, [], completion=boom).run(CASE, CTX)
    assert r2.error_kind == "provider" and "TimeoutError" in (r2.error or "")


def test_langgraph_message_parsing():
    class AIMessage:
        def __init__(self, content="", tool_calls=None, usage=None):
            self.content, self.tool_calls, self.usage_metadata = content, tool_calls or [], usage or {}

    class ToolMessage:
        def __init__(self, tool_call_id, content, status="success"):
            self.tool_call_id, self.content, self.status = tool_call_id, content, status

    msgs = [
        AIMessage(
            tool_calls=[{"name": "lookup", "args": {"id": 1}, "id": "t1"}],
            usage={"input_tokens": 5, "output_tokens": 2},
        ),
        ToolMessage("t1", "found"),
        AIMessage("all done", usage={"input_tokens": 4, "output_tokens": 1}),
    ]
    r = result_from_langgraph_messages(msgs, "m")
    assert r.tool_names == ["lookup"] and r.tool_calls[0].result == "found" and r.final_output == "all done"
    assert r.steps == 2 and r.total_tokens == 12
    err = result_from_langgraph_messages([msgs[0], ToolMessage("t1", "boom", "error")])
    assert err.tool_calls[0].error == "boom"
    assert os.name  # keep import used on all platforms
