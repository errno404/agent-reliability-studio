"""Adapter contract and the sample runner (execution error != quality failure)."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from .assertions import evaluate_all
from .judge import Judge
from .models import (
    AgentResult,
    AssertionResult,
    Case,
    Dataset,
    Layer,
    SampleResult,
    SampleStatus,
    Severity,
)
from .pricing import PriceTable
from .taxonomy import classify_failure
from .trajectory import trajectory_checks


@dataclass
class RunContext:
    run_id: str
    sample_index: int
    seed: int
    extra: dict[str, Any] = field(default_factory=dict)


class AgentAdapter(Protocol):
    """Framework-agnostic contract every system under test implements."""

    name: str
    version: str

    def run(self, case: Case, ctx: RunContext) -> AgentResult: ...


class CallableAdapter:
    """Wrap any Python callable ``fn(case, ctx) -> AgentResult``."""

    def __init__(self, name: str, version: str, fn: Callable[[Case, RunContext], AgentResult]):
        self.name, self.version, self._fn = name, version, fn

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        return self._fn(case, ctx)


def derive_status(assertions: list[AssertionResult], result: AgentResult) -> SampleStatus:
    if result.error:
        return SampleStatus.EXECUTION_ERROR
    if any(a.invalid for a in assertions):
        return SampleStatus.INVALID
    gating = [a for a in assertions if a.gating and not a.skipped]
    if not gating:
        return SampleStatus.SKIPPED
    return SampleStatus.PASSED if all(a.passed for a in gating) else SampleStatus.FAILED


def score_result(
    case: Case,
    result: AgentResult,
    sample_index: int = 0,
    seed: int | None = None,
    judge: Judge | None = None,
    judge_admitted: bool = False,
) -> SampleResult:
    """Pure scoring of an already-produced AgentResult (also used for rescoring stored runs)."""
    assertions = evaluate_all(case, result) + trajectory_checks(case, result)
    judge_record: dict[str, Any] | None = None
    judge_uncertain = False
    spec = case.rubric.get("judge") if case.rubric else None
    if spec and spec.get("required") and not result.error and (judge is None or not judge_admitted):
        # A REQUIRED semantic check may not silently disappear. Without an admitted judge the sample is INVALID
        # (unavailable evidence): never "passed" and never quietly skipped.
        assertions.append(
            AssertionResult(
                name="judge:required",
                type="llm_judge",
                layer=Layer.OUTCOME,
                gating=True,
                passed=False,
                invalid=True,
                expected="an admitted judge",
                actual="none" if judge is None else "judge not admitted",
                evidence="required judge criterion cannot be evaluated: no admitted judge is configured",
                severity=Severity.HIGH,
                label="evaluator_uncertainty",
            )
        )
    if judge is not None and spec and not result.error:
        rubric_text = "\n".join(
            [f"MUST: {m}" for m in spec.get("must", [])] + [f"MUST_NOT: {m}" for m in spec.get("must_not", [])]
        )
        out = judge.evaluate(rubric_text, case.input, result.final_output)
        judge_record = {
            "backend": judge.config.backend,
            "model": judge.config.model,
            "prompt_hash": judge.config.prompt_hash,
            "dimension": judge.config.dimension,
            "rubric_version": judge.config.rubric_version,
            "admitted": judge_admitted,
            "attempts": out.attempts,
            "error": out.error,
            "verdict": out.verdict.model_dump() if out.verdict else None,
        }
        gate_it = bool(spec.get("gating", True)) and judge_admitted
        if out.verdict is None:
            judge_uncertain = True  # judge failure is not an agent failure
            if gate_it:
                # A gating (admitted) judge that cannot answer must not let the case pass by omission:
                # the sample becomes an execution error (excluded from quality metrics, counted by validation).
                result.error, result.error_kind = f"judge failure: {out.error}", "judge"
        else:
            gate = bool(spec.get("gating", True)) and judge_admitted  # never gate on uncalibrated judge
            assertions.append(
                AssertionResult(
                    name=f"judge:{judge.config.dimension}",
                    type="llm_judge",
                    layer=Layer.OUTCOME,
                    gating=gate,
                    passed=out.verdict.passed,
                    expected="pass",
                    actual=out.verdict.label,
                    evidence=out.verdict.rationale,
                    severity=Severity.MEDIUM,
                    label="incorrect_final_answer",
                )
            )
    status = derive_status(assertions, result)
    labels = classify_failure(status, assertions, result, judge_uncertain)
    return SampleResult(
        case_id=case.id,
        category=case.category,
        sample_index=sample_index,
        status=status,
        assertions=assertions,
        result=result,
        failure_labels=labels,
        judge=judge_record,
        seed=seed,
    )


def execute_sample(
    adapter: AgentAdapter,
    case: Case,
    run_id: str,
    sample_index: int,
    seed: int,
    price_table: PriceTable | None = None,
    judge: Judge | None = None,
    judge_admitted: bool = False,
) -> SampleResult:
    ctx = RunContext(run_id=run_id, sample_index=sample_index, seed=seed)
    try:
        result = adapter.run(case, ctx)
    except Exception as exc:  # adapter crash => execution error, never a quality failure
        result = AgentResult(
            error=f"{type(exc).__name__}: {exc}"[:500],
            error_kind="adapter",
            metadata={"traceback_tail": traceback.format_exc()[-600:]},
        )
    if price_table is not None and result.cost_usd is None and not result.error:
        result.cost_usd = price_table.cost(result.model, result.input_tokens, result.output_tokens)
    return score_result(case, result, sample_index, seed, judge, judge_admitted)


def execute_run(
    adapter: AgentAdapter,
    dataset: Dataset,
    run_id: str,
    samples: int = 1,
    seed: int = 0,
    concurrency: int = 1,
    price_table: PriceTable | None = None,
    judge: Judge | None = None,
    judge_admitted: bool = False,
    on_sample: Callable[[SampleResult], None] | None = None,
) -> list[SampleResult]:
    jobs = [(c, i) for c in dataset.cases for i in range(samples)]

    def one(job: tuple[Case, int]) -> SampleResult:
        case, i = job
        s = execute_sample(adapter, case, run_id, i, seed, price_table, judge, judge_admitted)
        if on_sample:
            on_sample(s)
        return s

    if concurrency <= 1:
        return [one(j) for j in jobs]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        return list(pool.map(one, jobs))
