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
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import AgentResult, Case, ToolCall
from .runner import RunContext

# ---------------------------------------------------------------- sandbox --


def run_command(
    argv: list[str], cwd: Path, timeout_s: float, env: dict[str, str] | None = None, stdin: str | None = None
) -> tuple[int | None, str, str, bool]:
    """Run a command with a timeout and kill the WHOLE process tree on expiry.

    Returns (exit_code | None, stdout, stderr, timed_out). Never uses a shell.
    """
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(stdin, timeout=timeout_s)
        return proc.returncode, out, err, False
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        out, err = proc.communicate()
        return None, out or "", err or "", True


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
                shutil.copytree(self.fixtures_root / str(src), work)
            else:
                work.mkdir()
            before = snapshot(work)
            t0 = time.monotonic()
            code, out, err, timed_out = run_command(self.build_argv(case.input), work, self.timeout_s)
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
                c, o, e, to = run_command(list(cmd), work, 120)
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
