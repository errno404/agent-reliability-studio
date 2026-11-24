"""Shared harness for the deterministic reference agents.

These agents are *policy-engine simulators*: scripted behaviour plus seeded fault injection.
They are NOT LLM outputs. The evaluation machinery around them (traces, assertions, statistics)
is real; the point is a reproducible system under test that works with zero API keys.
Infrastructure only lives here; behaviour lives in the frozen per-version directories.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evalcore import semconv as sc
from evalcore.models import AgentResult, ToolCall
from evalcore.redaction import Redactor
from evalcore.tracing import TraceRecorder


def unit_float(*parts: Any) -> float:
    """Deterministic float in [0,1) from arbitrary parts (stable across processes/platforms)."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def dir_hash(path: Path) -> str:
    """Hash of every file in a pinned version directory (code + prompt + metadata)."""
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.relative_to(path).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


class Runtime:
    """Per-sample runtime: virtual clock, OTel spans, tool/model call recording, seeded chance."""

    def __init__(
        self,
        *,
        agent: str,
        version: str,
        model: str,
        prompt_hash: str,
        run_id: str,
        case_id: str,
        sample_index: int,
        seed: int,
        noise: dict[str, float],
        redactor: Redactor | None = None,
        secrets: tuple[str, ...] = (),
    ):
        self.agent, self.version, self.model, self.noise = agent, version, model, noise
        self.run_id, self.case_id, self.sample_index, self.seed = run_id, case_id, sample_index, seed
        self.prompt_hash = prompt_hash
        self.trace = TraceRecorder(redactor or Redactor(known_secrets=secrets))
        self.calls: list[ToolCall] = []
        self.in_tokens = self.out_tokens = self.steps = 0
        self.state: dict[str, Any] = {}
        self._root: Any = None
        self._root_cm: Any = None

    # ----------------------------------------------------------- randomness
    def roll(self, event: str) -> float:
        return unit_float(self.seed, self.case_id, self.sample_index, self.version, event)

    def chance(self, event: str) -> bool:
        p = self.noise.get(event, 0.0)
        return p > 0 and self.roll(event) < p

    def jitter(self, base_ms: float, event: str, spread: float = 0.35) -> float:
        return base_ms * (1 + (self.roll("lat:" + event) - 0.5) * 2 * spread)

    # --------------------------------------------------------------- spans
    def start(self, user_input: str) -> None:
        self._root_cm = self.trace.span(
            sc.span_name(sc.OP_INVOKE_AGENT, self.agent),
            {
                sc.OPERATION_NAME: sc.OP_INVOKE_AGENT,
                sc.AGENT_NAME: self.agent,
                sc.AGENT_VERSION: self.version,
                sc.PROVIDER_NAME: "synthetic",
                sc.REQUEST_MODEL: self.model,
                sc.ARS_RUN_ID: self.run_id,
                sc.ARS_CASE_ID: self.case_id,
                sc.ARS_SAMPLE_INDEX: self.sample_index,
                sc.ARS_PROMPT_HASH: self.prompt_hash,
            },
        )
        self._root = self._root_cm.__enter__()

    def finish(self) -> None:
        if self._root_cm is not None:
            self._root_cm.__exit__(None, None, None)
            self._root_cm = None

    def model_call(
        self, purpose: str, in_tokens: int, out_tokens: int, base_ms: float = 420.0, finish: str = "stop"
    ) -> None:
        in_t = int(in_tokens * (1 + (self.roll("tok_in:" + str(self.steps)) - 0.5) * 0.1))
        out_t = int(out_tokens * (1 + (self.roll("tok_out:" + str(self.steps)) - 0.5) * 0.1))
        with self.trace.span(
            sc.span_name(sc.OP_CHAT, self.model),
            {
                sc.OPERATION_NAME: sc.OP_CHAT,
                sc.PROVIDER_NAME: "synthetic",
                sc.REQUEST_MODEL: self.model,
                sc.RESPONSE_MODEL: self.model,
                sc.INPUT_TOKENS: in_t,
                sc.OUTPUT_TOKENS: out_t,
                sc.FINISH_REASONS: finish,
                "ars.purpose": purpose,
            },
        ):
            self.trace.advance(self.jitter(base_ms, f"chat{self.steps}"))
        self.in_tokens += in_t
        self.out_tokens += out_t
        self.steps += 1

    def tool(
        self,
        name: str,
        fn: Callable[..., Any],
        arguments: dict[str, Any],
        base_ms: float = 90.0,
        retrieval: bool = False,
    ) -> ToolCall:
        """Execute a tool, recording the call, its span, and any error (as data, never raised)."""
        op = sc.OP_RETRIEVAL if retrieval else sc.OP_EXECUTE_TOOL
        call = ToolCall(name=name, arguments=arguments)
        with self.trace.span(
            sc.span_name(op, name), {sc.OPERATION_NAME: op, sc.TOOL_NAME: name, sc.TOOL_CALL_ARGUMENTS: arguments}
        ) as span:
            self.trace.advance(self.jitter(base_ms, f"tool{len(self.calls)}"))
            try:
                call.result = fn(**arguments)
                if isinstance(call.result, dict) and call.result.get("error"):
                    call.error = str(call.result["error"])
            except Exception as exc:  # tool failure is observable data
                call.error = f"{type(exc).__name__}: {exc}"[:200]
            call.latency_ms = self.trace.now_ms
            self.trace.set_attr(span, sc.TOOL_CALL_RESULT, call.result if call.error is None else {"error": call.error})
            if call.error:
                self.trace.mark_error(span, call.error)
                span.set_attribute(sc.ERROR_TYPE, "tool_error")
        self.calls.append(call)
        return call

    # -------------------------------------------------------------- result
    def result(
        self,
        final: str,
        *,
        turns: int = 1,
        error: str | None = None,
        error_kind: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.finish()
        res = AgentResult(
            final_output=final,
            tool_calls=self.calls,
            turns=turns,
            steps=self.steps + len(self.calls),
            latency_ms=round(self.trace.now_ms, 3),
            input_tokens=self.in_tokens,
            output_tokens=self.out_tokens,
            model=self.model,
            state=self.state,
            spans=self.trace.records(),
            error=error,
            error_kind=error_kind,
            metadata={"synthetic": True, "agent": self.agent, "agent_version": self.version, **(extra or {})},
        )
        # round-trip through JSON so everything is plain data
        return AgentResult.model_validate(json.loads(res.model_dump_json()))
