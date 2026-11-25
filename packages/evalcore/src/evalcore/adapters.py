"""Concrete adapters: Claude Code CLI, LiteLLM (tool loop) and LangGraph message parsing.

All adapters convert failures of *infrastructure* (timeout, crash, provider error) into
``AgentResult.error`` so they are execution errors, never quality failures.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import AgentResult, Case, ToolCall
from .runner import RunContext

# ---------------------------------------------------------------- sandbox --


MAX_OUTPUT_BYTES = 1_000_000  # captured per stream; the process is also bounded by RLIMIT_FSIZE on its output files
LIMITS = {"cpu_s": 60, "fsize_mb": 16, "nproc": 256}  # applied by the launcher; best effort per platform

_LAUNCHER = (
    "import os,resource,sys\n"
    "cpu,fs,np=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3])\n"
    "def lim(r,v):\n"
    "    try: resource.setrlimit(r,(v,v))\n"
    "    except (ValueError,OSError): pass\n"
    "lim(resource.RLIMIT_CPU,cpu); lim(resource.RLIMIT_FSIZE,fs*1024*1024)\n"
    "if sys.platform.startswith('linux'): lim(resource.RLIMIT_NPROC,np)\n"
    "os.execvp(sys.argv[4],sys.argv[4:])\n"
)


def run_command(
    argv: list[str], cwd: Path, timeout_s: float, env: dict[str, str] | None = None, stdin: str | None = None
) -> tuple[int | None, str, str, bool]:
    """Run a command with limits and kill the WHOLE process tree on expiry.

    Returns (exit_code | None, stdout, stderr, timed_out). Never uses a shell. CPU time and the size of any file the process writes
    (including its captured output) are bounded by rlimits; captured output is truncated to ``MAX_OUTPUT_BYTES`` per stream.

    THIS IS NOT A SANDBOX. It does not restrict the filesystem outside ``cwd`` or the network, and on macOS it cannot cap memory.
    It is only ever used for repo-authored fixtures and pinned test commands (see ``trusted_test_command``), never for
    user-supplied text.
    """
    import tempfile

    wrapped = [
        sys.executable,
        "-c",
        _LAUNCHER,
        str(LIMITS["cpu_s"]),
        str(LIMITS["fsize_mb"]),
        str(LIMITS["nproc"]),
        *argv,
    ]
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        proc = subprocess.Popen(
            wrapped,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=fo,
            stderr=fe,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            proc.communicate(stdin, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.communicate()

        def read(f) -> str:  # type: ignore[no-untyped-def]
            f.seek(0)
            return f.read(MAX_OUTPUT_BYTES).decode("utf-8", "replace")

        return (None if timed_out else proc.returncode), read(fo), read(fe), timed_out


TRUSTED_TEST_MODULES = ("pytest", "unittest")


def trusted_test_command(argv: list[str]) -> list[str]:
    """Allow only ``PYTHON -m pytest|unittest <relative paths / simple flags>``; dataset text is never a general shell.

    Raises ValueError for anything else: other executables, ``-c``, absolute or parent paths, shell metacharacters.
    """
    if len(argv) < 3 or argv[0] != "PYTHON" or argv[1] != "-m" or argv[2] not in TRUSTED_TEST_MODULES:
        raise ValueError(f"untrusted test command {argv[:3]!r}: only 'PYTHON -m pytest|unittest ...' is allowed")
    for a in argv[3:]:
        if (
            a.startswith("/")
            or ".." in Path(a).parts
            or any(ch in a for ch in ";|&$`<>\n")
            or a in ("-c", "-p", "--rootdir")
        ):
            raise ValueError(f"untrusted test argument {a!r}")
    return argv


def inside(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``; reject absolute paths, traversal, and anything that resolves through a symlink outside."""
    if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError(f"path escapes the workspace: {rel!r}")
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes the workspace: {rel!r}")
    return target


def assert_no_symlinks(root: Path) -> None:
    """A fixture repository may not contain symlinks (they could point outside the sandbox directory)."""
    bad = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_symlink()]
    if bad:
        raise ValueError(f"symlinks are not allowed in a workspace: {bad[:3]}")


def safe_env() -> dict[str, str]:
    """Minimal environment for subprocesses: no inherited secrets (admin token, database URL, API keys)."""
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TERM", "USER")
    return {k: v for k, v in os.environ.items() if k in keep}


def snapshot(root: Path) -> dict[str, str]:
    """Relative path -> content hash for every regular file under root."""
    snap: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts:
            snap[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


# ---------------------------------------------------------- Claude Code ---
class ClaudeCodeAdapter:
    """Evaluate the local Claude Code CLI (``claude -p --output-format json``).

    Uses the user's own authenticated CLI session. Subscription-backed runs are NOT billed
    per-token, so ``total_cost_usd`` from the CLI is stored only as an API-equivalent estimate
    in ``metadata`` (never shown as money the user paid). Runs inside a throw-away workspace
    copied from ``case.fixture['workspace']``; local/admin use only.
    """

    def __init__(
        self,
        name: str = "claude-code",
        version: str = "cli",
        binary: str | None = None,
        model: str | None = None,
        timeout_s: float = 300.0,
        allowed_tools: list[str] | None = None,
        permission_mode: str = "acceptEdits",
        fixtures_root: Path | None = None,
        extra_args: list[str] | None = None,
    ):
        self.name, self.version = name, version
        self.binary = binary or shutil.which("claude")
        self.model, self.timeout_s = model, timeout_s
        self.allowed_tools, self.permission_mode = allowed_tools, permission_mode
        self.fixtures_root = fixtures_root
        self.extra_args = extra_args or []

    @property
    def available(self) -> bool:
        return bool(self.binary and Path(self.binary).exists())

    def build_argv(self, prompt: str) -> list[str]:
        assert self.binary
        argv = [
            self.binary,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            self.permission_mode,
        ]
        if self.model:
            argv += ["--model", self.model]
        if self.allowed_tools:
            argv += ["--allowedTools", *self.allowed_tools]
        return argv + self.extra_args

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        if not self.available:
            return AgentResult(error="claude CLI not found on PATH", error_kind="adapter")
        src = case.fixture.get("workspace")
        with tempfile.TemporaryDirectory(prefix="ars-cc-") as tmp:
            work = Path(tmp) / "ws"
            if src and self.fixtures_root:
                root = self.fixtures_root.resolve()
                srcdir = (root / str(src)).resolve()
                if not srcdir.is_relative_to(
                    root
                ):  # a dataset must not point the sandbox at arbitrary host directories
                    return AgentResult(error="fixture workspace escapes the fixtures root", error_kind="adapter")
                shutil.copytree(srcdir, work, symlinks=True)
            else:
                work.mkdir()
            before = snapshot(work)
            t0 = time.monotonic()
            code, out, err, timed_out = run_command(self.build_argv(case.input), work, self.timeout_s, env=safe_env())
            latency = (time.monotonic() - t0) * 1000
            if timed_out:
                return AgentResult(
                    error=f"timeout after {self.timeout_s}s",
                    error_kind="timeout",
                    latency_ms=latency,
                    metadata={"stderr": err[-500:]},
                )
            res = self.parse_output(out, code, err)
            res.latency_ms = latency
            after = snapshot(work)
            res.changed_files = changed_files(before, after)
            res.workspace_files = sorted(after)
            for name, cmd in (case.fixture.get("commands") or {}).items():
                c, o, e, to = run_command(list(cmd), work, 120, env=safe_env())
                res.commands[name] = {"exit_code": c, "stdout": o[-1000:], "stderr": e[-500:], "timed_out": to}
            return res

    @staticmethod
    def parse_output(stdout: str, code: int | None, stderr: str) -> AgentResult:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return AgentResult(
                error=f"unparseable CLI output (exit {code}): {stderr[-300:] or stdout[-300:]}", error_kind="adapter"
            )
        usage = data.get("usage") or {}
        model_usage = data.get("modelUsage") or {}
        model = next(iter(model_usage), None)
        if data.get("is_error") or (code not in (0, None)):
            return AgentResult(
                error=str(data.get("result") or stderr)[:400],
                error_kind="provider",
                model=model,
                metadata={"exit_code": code},
            )
        return AgentResult(
            final_output=str(data.get("result", "")),
            turns=int(data.get("num_turns", 1)),
            input_tokens=int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            model=model,
            cost_usd=None,
            metadata={
                "api_equivalent_cost_usd": data.get("total_cost_usd"),
                "session_id": data.get("session_id"),
                "cost_note": "API-equivalent estimate; subscription runs are not billed per token",
            },
        )


# ---------------------------------------------------------------- LiteLLM --
class LiteLLMAdapter:
    """API-backed tool-using agent via LiteLLM chat completions (optional dependency)."""

    def __init__(
        self,
        name: str,
        version: str,
        model: str,
        system_prompt: str,
        tools: dict[str, Callable[..., Any]],
        tool_specs: list[dict[str, Any]],
        max_steps: int = 8,
        completion: Callable[..., Any] | None = None,
    ):
        self.name, self.version, self.model = name, version, model
        self.system_prompt, self.tools, self.tool_specs = system_prompt, tools, tool_specs
        self.max_steps, self._completion = max_steps, completion

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        fn = self._completion
        if fn is None:
            try:
                import litellm  # pyright: ignore[reportMissingImports]
            except ImportError:
                return AgentResult(error="litellm not installed (pip install evalcore[litellm])", error_kind="adapter")
            fn = litellm.completion
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": case.input},
        ]
        res = AgentResult(model=self.model)
        t0 = time.monotonic()
        try:
            for _ in range(self.max_steps):
                resp = fn(model=self.model, messages=msgs, tools=self.tool_specs or None, temperature=0)
                res.steps += 1
                u = getattr(resp, "usage", None)
                res.input_tokens += int(getattr(u, "prompt_tokens", 0) or 0)
                res.output_tokens += int(getattr(u, "completion_tokens", 0) or 0)
                m = resp.choices[0].message
                calls = getattr(m, "tool_calls", None) or []
                if not calls:
                    res.final_output = m.content or ""
                    break
                msgs.append(
                    {
                        "role": "assistant",
                        "content": m.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                            }
                            for tc in calls
                        ],
                    }
                )
                for tc in calls:
                    args = json.loads(tc.function.arguments or "{}")
                    call = ToolCall(name=tc.function.name, arguments=args)
                    try:
                        call.result = self.tools[tc.function.name](**args)
                    except Exception as exc:
                        call.error = f"{type(exc).__name__}: {exc}"[:200]
                    res.tool_calls.append(call)
                    payload = json.dumps(call.result if call.error is None else call.error, default=str)
                    msgs.append({"role": "tool", "tool_call_id": tc.id, "content": payload})
        except Exception as exc:
            res.error, res.error_kind = f"{type(exc).__name__}: {exc}"[:400], "provider"
        res.latency_ms = (time.monotonic() - t0) * 1000
        return res


# -------------------------------------------------------------- LangGraph --
def result_from_langgraph_messages(messages: list[Any], model: str | None = None) -> AgentResult:
    """Convert a LangGraph/LangChain message list into an AgentResult by duck typing.

    Reads AI message ``tool_calls`` and matching tool-message results plus ``usage_metadata``.
    Only observable content is read; no reasoning content is touched.
    """
    res = AgentResult(model=model)
    pending: dict[str, ToolCall] = {}
    final = ""
    for m in messages:
        kind = type(m).__name__
        if kind == "AIMessage":
            res.steps += 1
            um = getattr(m, "usage_metadata", None) or {}
            res.input_tokens += int(um.get("input_tokens", 0))
            res.output_tokens += int(um.get("output_tokens", 0))
            for tc in getattr(m, "tool_calls", None) or []:
                call = ToolCall(name=tc["name"], arguments=dict(tc.get("args") or {}))
                pending[tc.get("id", f"{len(pending)}")] = call
                res.tool_calls.append(call)
            if not getattr(m, "tool_calls", None):
                final = str(getattr(m, "content", ""))
        elif kind == "ToolMessage":
            call = pending.get(getattr(m, "tool_call_id", ""))
            if call is not None:
                content = getattr(m, "content", None)
                if getattr(m, "status", "success") == "error":
                    call.error = str(content)[:300]
                else:
                    call.result = content
    res.final_output = final
    return res


# ------------------------------------------------- Claude Code as a tool-using research agent (live LLM)
def _strip_mcp_prefix(name: str) -> str:
    """`mcp__fixture__web_search` -> `web_search` (the server prefix is an transport detail, not the tool identity)."""
    return name.split("__", 2)[2] if name.startswith("mcp__") and name.count("__") >= 2 else name


def parse_claude_stream(
    events: list[tuple[float, dict[str, Any]]], redactor: Any = None, model_requested: str | None = None
) -> AgentResult:
    """Convert Claude Code ``--output-format stream-json`` events into an :class:`AgentResult`.

    ``events`` are ``(arrival_seconds_since_start, event_dict)``. Nothing is synthesized: tool calls come from real
    ``tool_use`` blocks, results from the matching ``tool_result`` blocks, timings from event arrival, tokens/model from
    the provider-reported ``result``/``modelUsage``. Reasoning/thinking content is never read or stored.
    """
    from . import semconv as sc
    from .redaction import Redactor
    from .tracing import TraceRecorder

    rd = redactor or Redactor()
    rec = TraceRecorder(rd)
    res = AgentResult(model=None)
    pending: dict[str, tuple[ToolCall, float]] = {}
    init_model: str | None = None
    final_text = ""
    result_event: dict[str, Any] | None = None
    t_prev = 0.0
    with rec.span(
        sc.span_name(sc.OP_INVOKE_AGENT, "claude-code-research"),
        {sc.OPERATION_NAME: sc.OP_INVOKE_AGENT, sc.PROVIDER_NAME: "anthropic", sc.AGENT_NAME: "claude-code-research"},
    ) as root:
        for t, ev in events:
            rec.advance(max(0.0, (t - t_prev) * 1000))
            t_prev = t
            typ = ev.get("type")
            if typ == "system" and ev.get("subtype") == "init":
                init_model = ev.get("model")
            elif typ == "assistant":
                for b in ev.get("message", {}).get("content") or []:
                    if b.get("type") == "tool_use":
                        call = ToolCall(
                            name=_strip_mcp_prefix(str(b.get("name", ""))), arguments=dict(b.get("input") or {})
                        )
                        pending[str(b.get("id"))] = (call, t)
                        res.tool_calls.append(call)
                    elif b.get("type") == "text":
                        final_text = str(b.get("text", ""))  # the last text block of the last assistant turn
                res.steps += 1
            elif typ == "user":
                for b in (
                    (ev.get("message", {}).get("content") or [])
                    if isinstance(ev.get("message", {}).get("content"), list)
                    else []
                ):
                    if b.get("type") != "tool_result":
                        continue
                    call, started = pending.pop(str(b.get("tool_use_id")), (None, t))
                    if call is None:
                        continue
                    content = b.get("content")
                    text = (
                        content
                        if isinstance(content, str)
                        else "".join(c.get("text", "") for c in content or [] if isinstance(c, dict))
                    )
                    try:
                        parsed: Any = json.loads(text)
                        parsed = (
                            json.loads(parsed["result"])
                            if isinstance(parsed, dict) and isinstance(parsed.get("result"), str)
                            else parsed
                        )
                    except (json.JSONDecodeError, TypeError, KeyError):
                        parsed = text
                    call.result = parsed
                    if b.get("is_error") or (isinstance(parsed, dict) and parsed.get("ok") is False):
                        call.error = str((parsed.get("error") if isinstance(parsed, dict) else parsed) or "tool error")[
                            :300
                        ]
                    call.latency_ms = round((t - started) * 1000, 1)
                    op = sc.OP_RETRIEVAL if call.name in ("web_search", "web_fetch") else sc.OP_EXECUTE_TOOL
                    # tool span reconstructed from the REAL start/end arrival times
                    with rec.span(
                        sc.span_name(op, call.name),
                        {sc.OPERATION_NAME: op, sc.TOOL_NAME: call.name, sc.TOOL_CALL_ARGUMENTS: call.arguments},
                    ) as sp:
                        rec.advance(0)
                        rec.set_attr(sp, sc.TOOL_CALL_RESULT, call.result if not call.error else {"error": call.error})
                        if call.error:
                            rec.mark_error(sp, call.error)
            elif typ == "result":
                result_event = ev
        usage = (result_event or {}).get("usage") or {}
        mu = (result_event or {}).get("modelUsage") or {}
        resolved = next(iter(mu), None) or init_model
        res.model = resolved
        res.input_tokens = (
            int(usage.get("input_tokens", 0))
            + int(usage.get("cache_read_input_tokens", 0))
            + int(usage.get("cache_creation_input_tokens", 0))
        )
        res.output_tokens = int(usage.get("output_tokens", 0))
        res.turns = int((result_event or {}).get("num_turns", 1))
        res.latency_ms = float((result_event or {}).get("duration_ms") or (t_prev * 1000))
        rec.set_attr(root, sc.REQUEST_MODEL, model_requested or "")
        rec.set_attr(root, sc.RESPONSE_MODEL, resolved or "")
        rec.set_attr(root, sc.INPUT_TOKENS, res.input_tokens)
        rec.set_attr(root, sc.OUTPUT_TOKENS, res.output_tokens)
    if result_event is None:
        res.error, res.error_kind = "no result event in the CLI stream (process ended early)", "adapter"
    elif result_event.get("is_error") or result_event.get("subtype") != "success":
        res.error, res.error_kind = str(result_event.get("result") or result_event.get("subtype"))[:400], "provider"
    else:
        res.final_output = str(result_event.get("result") or final_text)
    res.metadata = {
        "execution_kind": "live",
        "provider": "anthropic",
        "model_requested": model_requested,
        "model_resolved": resolved,
        "api_equivalent_cost_usd": (result_event or {}).get("total_cost_usd"),
        "duration_api_ms": (result_event or {}).get("duration_api_ms"),
        "cost_note": "API-equivalent estimate reported by the CLI; subscription runs are not billed per token",
    }
    res.spans = rec.records()
    return res


class ClaudeCodeToolAgent:
    """A real LLM agent: Claude Code with ONLY the supplied MCP tools (no shell, files or web), isolated from user settings.

    The model's decisions and answers are the provider's; the tool environment is the frozen synthetic fixture web. Run with
    the user's own authenticated CLI (no credentials are read or extracted). Local/admin execution only.
    """

    agent_hash: str = ""  # set by the factory: content hash of the frozen version directory
    prompt_hash: str = ""
    requested_model: str = ""

    def __init__(
        self,
        name: str,
        version: str,
        system_prompt: str,
        mcp_servers: dict[str, Any],
        allowed_tools: list[str],
        model: str = "haiku",
        timeout_s: float = 180.0,
        max_budget_usd: float = 0.50,
        binary: str | None = None,
        redactor: Any = None,
    ):
        self.name, self.version, self.system_prompt = name, version, system_prompt
        self.mcp_servers, self.allowed_tools, self.model = mcp_servers, allowed_tools, model
        self.timeout_s, self.max_budget_usd, self.redactor = timeout_s, max_budget_usd, redactor
        self.binary = binary or os.environ.get("ARS_CLAUDE_BIN") or shutil.which("claude")

    @property
    def available(self) -> bool:
        return bool(self.binary and Path(self.binary).exists())

    def build_argv(self, prompt: str) -> list[str]:
        assert self.binary
        return [
            self.binary,
            "-p",  # the task text is sent on stdin, never as an argv element (a leading "-" cannot be parsed as a flag)
            "--output-format",
            "stream-json",
            "--verbose",
            "--mcp-config",
            json.dumps({"mcpServers": self.mcp_servers}),
            "--strict-mcp-config",
            "--tools",
            "",
            "--allowedTools",
            *self.allowed_tools,
            "--model",
            self.model,
            "--no-session-persistence",
            "--system-prompt",
            self.system_prompt,
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--settings",
            '{"hooks":{},"enabledPlugins":{}}',
            "--max-budget-usd",
            f"{self.max_budget_usd:.2f}",
        ]

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        if not self.available:
            return AgentResult(error="claude CLI not found", error_kind="adapter", metadata={"execution_kind": "live"})
        with tempfile.TemporaryDirectory(prefix="ars-live-") as tmp:
            events: list[tuple[float, dict[str, Any]]] = []
            t0 = time.monotonic()
            proc = subprocess.Popen(
                self.build_argv(case.input),
                cwd=tmp,
                env=safe_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                assert proc.stdin is not None
                proc.stdin.write(case.input)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass  # the process died early; its exit status is reported below
            timer = threading.Timer(self.timeout_s, lambda: _kill_group(proc))
            timer.start()
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.strip()
                    if line.startswith("{"):
                        try:
                            events.append((time.monotonic() - t0, json.loads(line)))
                        except json.JSONDecodeError:
                            continue
                proc.wait()
            finally:
                timed_out = (
                    not timer.is_alive()
                    and proc.returncode not in (0, None)
                    and (time.monotonic() - t0) >= self.timeout_s
                )
                timer.cancel()
            if timed_out:
                return AgentResult(
                    error=f"timeout after {self.timeout_s}s",
                    error_kind="timeout",
                    latency_ms=(time.monotonic() - t0) * 1000,
                    metadata={"execution_kind": "live"},
                )
            res = parse_claude_stream(events, self.redactor, self.model)
            if res.error and proc.returncode not in (0, None) and not events:
                res.error = (
                    f"{res.error}; exit {proc.returncode}; stderr: {(proc.stderr.read() if proc.stderr else '')[-200:]}"
                )
            return res


def _kill_group(proc: subprocess.Popen[str]) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
