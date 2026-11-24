"""Ingest an Inspect AI evaluation log (JSON) into our normalized run format.

Works on the plain JSON log (no ``inspect-ai`` import needed). Mapping:

* sample ``id`` -> case_id; ``epoch`` (1-based) -> sample_index (0-based)
* sample ``error`` -> EXECUTION ERROR (never a quality failure)
* each scorer's ``Score.value`` -> one assertion; CORRECT/1/True = pass, INCORRECT/0/False = fail
* ``output.completion`` -> final output; assistant ``tool_calls`` -> our tool-call records
* ``model_usage`` -> token counts; ``total_time`` -> latency
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evalcore import RunManifest, SampleResult
from evalcore.hashing import hash_obj
from evalcore.models import AgentResult, AssertionResult, Layer, SampleStatus, ToolCall

_PASS = {"C", "CORRECT", "PASS", "TRUE", "1", "1.0", "YES"}
_FAIL = {"I", "INCORRECT", "FAIL", "FALSE", "0", "0.0", "NO"}


def _truthy(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v >= 1
    s = str(v).strip().upper()
    return True if s in _PASS else False if s in _FAIL else None


def _tool_calls(messages: list[dict[str, Any]]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            calls.append(ToolCall(name=str(tc.get("function", "")), arguments=dict(tc.get("arguments") or {})))
    return calls


def ingest_inspect_log(
    log: str | Path | dict[str, Any], run_id: str | None = None
) -> tuple[RunManifest, list[SampleResult]]:
    data: dict[str, Any] = log if isinstance(log, dict) else json.loads(Path(log).read_text())
    ev = data.get("eval", {})
    samples = data.get("samples") or []
    epochs = max((int(s.get("epoch", 1)) for s in samples), default=1)
    rid = run_id or f"inspect-{str(ev.get('run_id', hash_obj(data.get('eval', {}), 8)))[:16]}"
    results: list[SampleResult] = []
    for s in samples:
        usage = s.get("model_usage") or {}
        tin = sum(int(u.get("input_tokens", 0)) for u in usage.values())
        tout = sum(int(u.get("output_tokens", 0)) for u in usage.values())
        out = (s.get("output") or {}).get("completion", "") or ""
        err = (s.get("error") or {}).get("message") if isinstance(s.get("error"), dict) else None
        res = AgentResult(
            final_output=out,
            tool_calls=_tool_calls(s.get("messages") or []),
            input_tokens=tin,
            output_tokens=tout,
            latency_ms=float(s.get("total_time") or 0) * 1000,
            model=ev.get("model"),
            error=err,
            error_kind="inspect_error" if err else None,
            metadata={"source": "inspect_ai", "inspect_uuid": s.get("uuid")},
        )
        assertions: list[AssertionResult] = []
        for name, sc in (s.get("scores") or {}).items():
            ok = _truthy(sc.get("value"))
            if ok is None:
                continue
            assertions.append(
                AssertionResult(
                    name=f"inspect:{name}",
                    type="inspect_score",
                    layer=Layer.OUTCOME,
                    gating=True,
                    passed=ok,
                    expected="pass",
                    actual=str(sc.get("value")),
                    evidence=str(sc.get("explanation") or sc.get("answer") or "")[:300],
                )
            )
        status = (
            SampleStatus.EXECUTION_ERROR
            if err
            else SampleStatus.SKIPPED
            if not assertions
            else SampleStatus.PASSED
            if all(a.passed for a in assertions)
            else SampleStatus.FAILED
        )
        results.append(
            SampleResult(
                case_id=str(s.get("id")),
                category=str((s.get("metadata") or {}).get("category", "inspect")),
                sample_index=int(s.get("epoch", 1)) - 1,
                status=status,
                assertions=assertions,
                result=res,
                failure_labels=["execution_error"]
                if err
                else (["incorrect_final_answer"] if status == SampleStatus.FAILED else []),
            )
        )
    manifest = RunManifest(
        run_id=rid,
        run_type="inspect_import",
        agent=str(ev.get("task", "inspect-task")),
        agent_version=str(ev.get("task_version", "0")),
        dataset_name=str((ev.get("dataset") or {}).get("name") or ev.get("task", "")),
        dataset_hash=hash_obj(sorted(str(s.get("id")) for s in samples), 16),
        case_ids=sorted({str(s.get("id")) for s in samples}),
        samples_per_case=epochs,
        model_provider=str(ev.get("model", "")).split("/")[0],
        model=str(ev.get("model", "")),
        evaluator_version=f"inspect-ai {ev.get('packages', {}).get('inspect_ai', 'unknown')}",
    )
    return manifest, results
