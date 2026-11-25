import json
import sys
from pathlib import Path

from evalcore.adapters import ClaudeCodeToolAgent, parse_claude_stream
from evalcore.models import Case
from evalcore.runner import RunContext

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "claude_stream_real.json").read_text()
)  # captured from a real CLI run
CASE = Case(id="c", title="t", category="x", description="d", input="q")


def timed(events, step=0.5):
    return [(i * step, e) for i, e in enumerate(events)]


def test_parses_a_real_claude_code_stream_into_the_common_result():
    r = parse_claude_stream(timed(FIX), model_requested="haiku")
    assert r.error is None and r.metadata["execution_kind"] == "live"
    assert (
        r.tool_names == ["web_search", "web_fetch", "web_fetch"][: len(r.tool_calls)] or r.tool_names[0] == "web_search"
    )
    assert all(not n.startswith("mcp__") for n in r.tool_names)  # transport prefix stripped
    assert (
        r.model and r.model.startswith("claude-") and r.metadata["model_resolved"] == r.model
    )  # PROVIDER-reported model
    assert r.total_tokens > 0 and r.final_output and r.turns >= 1
    assert r.tool_calls[0].result is not None and r.tool_calls[0].latency_ms > 0  # timing from real event arrival
    root = next(s for s in r.spans if s.parent_id is None)
    assert (
        root.attributes["gen_ai.response.model"] == r.model
        and root.attributes["gen_ai.operation.name"] == "invoke_agent"
    )
    assert {s.kind for s in r.spans} >= {"agent", "retrieval"}
    assert r.metadata["api_equivalent_cost_usd"] is not None and r.cost_usd is None  # never presented as money paid


def test_reasoning_blocks_are_never_stored():
    ev = json.loads(json.dumps(FIX))
    for e in ev:
        if e.get("type") == "assistant":
            e["message"]["content"].insert(
                0, {"type": "thinking", "thinking": "SECRET-REASONING-CANARY", "signature": "x"}
            )
    blob = parse_claude_stream(timed(ev)).model_dump_json()
    assert "SECRET-REASONING-CANARY" not in blob


def test_missing_result_event_and_provider_errors_are_execution_errors():
    truncated = [e for e in FIX if e.get("type") != "result"]
    r = parse_claude_stream(timed(truncated))
    assert r.error and r.error_kind == "adapter"
    bad = json.loads(json.dumps(FIX))
    next(e for e in bad if e.get("type") == "result").update(
        {"is_error": True, "subtype": "error_max_budget_usd", "result": "budget"}
    )
    r2 = parse_claude_stream(timed(bad))
    assert r2.error_kind == "provider" and not r2.final_output


def test_failed_tool_result_is_recorded_as_a_tool_error_not_hidden():
    ev = json.loads(json.dumps(FIX))
    for e in ev:
        if e.get("type") == "user":
            for b in e["message"]["content"]:
                if b.get("type") == "tool_result":
                    b["content"] = json.dumps(
                        {"result": json.dumps({"ok": False, "status": 404, "error": "not found"})}
                    )
                    break
            break
    r = parse_claude_stream(timed(ev))
    assert r.tool_calls[0].error == "not found"
    assert any(s.status == "error" for s in r.spans)


def test_argv_isolates_the_agent_from_host_settings_and_tools(tmp_path):
    a = ClaudeCodeToolAgent(
        "r",
        "v1",
        "SYS",
        {"fixture": {"command": "x"}},
        ["mcp__fixture__web_search"],
        model="haiku",
        binary=sys.executable,
    )
    argv = a.build_argv("hello")
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--max-budget-usd") + 1] == "0.50" and "--bare" not in argv


def test_timeout_kills_the_process_group_and_is_an_execution_error(tmp_path):
    fake = tmp_path / "claude"
    fake.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    fake.chmod(0o755)
    a = ClaudeCodeToolAgent("r", "v1", "SYS", {}, [], binary=str(fake), timeout_s=0.8)
    r = a.run(CASE, RunContext("r", 0, 1))
    assert r.error_kind == "timeout" and r.metadata["execution_kind"] == "live"


def test_missing_binary_is_an_adapter_error():
    r = ClaudeCodeToolAgent("r", "v1", "SYS", {}, [], binary="/nonexistent/claude").run(CASE, RunContext("r", 0, 1))
    assert r.error_kind == "adapter"


def test_task_text_is_never_an_argv_element(tmp_path):
    """Regression (security review): a task starting with '-' must not be parseable as a CLI flag."""
    a = ClaudeCodeToolAgent("t", "v1", "sys", {}, [], binary=str(tmp_path / "claude"))
    argv = a.build_argv("--dangerously-skip-permissions please")
    assert not any("--dangerously-skip-permissions" in x for x in argv)


def _fake_cli(tmp_path, body: str) -> ClaudeCodeToolAgent:
    script = tmp_path / "fake_claude.py"
    script.write_text("import sys\n" + body)
    exe = tmp_path / "fake_claude"
    exe.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
    exe.chmod(0o755)
    return ClaudeCodeToolAgent("t", "v1", "sys", {}, [], binary=str(exe), timeout_s=20)


def test_large_stderr_does_not_deadlock_a_successful_run(tmp_path):
    """Regression (review): stderr was a pipe read only after wait(); >64KB made a good run look like a timeout."""
    ok = json.dumps(
        {"type": "result", "subtype": "success", "result": "fine", "is_error": False, "usage": {}, "num_turns": 1}
    )
    a = _fake_cli(tmp_path, f"sys.stderr.write('e' * 300000)\nprint({ok!r})\n")
    r = a.run(CASE, RunContext("r", 0, 0))
    assert r.error is None and r.final_output == "fine"


def test_undecodable_output_is_an_adapter_error_and_the_child_is_killed(tmp_path):
    a = _fake_cli(
        tmp_path,
        "import time,os\nsys.stdout.buffer.write(b'\\xff\\xfe\\n'); sys.stdout.flush()\nopen(os.path.join(os.path.dirname(__file__),'pid'),'w').write(str(os.getpid()))\ntime.sleep(60)\n",
    )
    r = a.run(CASE, RunContext("r", 0, 0))
    assert r.error and r.error_kind == "adapter"
    import os
    import time as _t

    pid = int((tmp_path / "pid").read_text())
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        _t.sleep(0.1)
    else:
        raise AssertionError("child process was orphaned")


def test_malformed_events_do_not_discard_a_valid_answer():
    ev = [
        {"type": "assistant", "message": None},
        {"type": "assistant", "message": {"content": ["not-a-dict", {"type": "text", "text": "answer"}]}},
        {"type": "user", "message": {"content": None}},
        {
            "type": "result",
            "subtype": "success",
            "result": "answer",
            "is_error": False,
            "usage": {"input_tokens": None},
            "num_turns": None,
        },
    ]
    r = parse_claude_stream([(i * 0.1, e) for i, e in enumerate(ev)], model_requested="haiku")
    assert r.error is None and r.final_output == "answer" and r.input_tokens == 0
