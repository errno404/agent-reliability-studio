"""Failure taxonomy: deterministic root-cause labels from structured evidence."""

from __future__ import annotations

from .models import AgentResult, AssertionResult, Layer, SampleStatus

TAXONOMY = (
    "incorrect_final_answer", "wrong_tool", "missing_tool", "forbidden_tool", "wrong_tool_arguments",
    "wrong_tool_order", "repeated_tool_loop", "error_thrashing", "premature_stop", "missing_clarification",
    "fabricated_claim", "grounding_failure", "policy_violation", "prompt_injection_failure",
    "state_mutation_failure", "latency_budget", "cost_budget", "execution_error", "evaluator_uncertainty",
)

_BY_TYPE = {
    "tool_called": "missing_tool", "tool_not_called": "forbidden_tool",
    "tool_arguments_match": "wrong_tool_arguments", "tool_sequence": "wrong_tool_order",
    "tool_call_count": "repeated_tool_loop", "max_steps": "repeated_tool_loop", "max_turns": "repeated_tool_loop",
    "max_latency_ms": "latency_budget", "max_cost_usd": "cost_budget", "max_input_tokens": "cost_budget",
    "max_output_tokens": "cost_budget", "max_total_tokens": "cost_budget",
    "state_equals": "state_mutation_failure", "state_contains": "state_mutation_failure",
    "output_contains": "incorrect_final_answer", "output_regex": "incorrect_final_answer",
    "output_json_schema": "incorrect_final_answer", "output_not_contains": "incorrect_final_answer",
    "command_exit": "incorrect_final_answer", "file_exists": "incorrect_final_answer",
    "file_not_changed": "policy_violation", "file_diff_max_files": "policy_violation",
}


def labels_for_assertion(a: AssertionResult) -> list[str]:
    if a.passed or a.skipped or not a.gating:
        return []
    if a.label in TAXONOMY:
        return [a.label]  # explicit author-provided root cause wins
    base = _BY_TYPE.get(a.type)
    labels = [base] if base else []
    if a.layer == Layer.POLICY and "policy_violation" not in labels:
        labels.append("policy_violation")
    return labels or ["incorrect_final_answer"]


def classify_failure(status: SampleStatus, assertions: list[AssertionResult], result: AgentResult,
                     judge_uncertain: bool = False) -> list[str]:
    if status == SampleStatus.EXECUTION_ERROR:
        return ["execution_error"]
    if status != SampleStatus.FAILED:
        return []
    labels: list[str] = []
    for a in assertions:
        for lab in labels_for_assertion(a):
            if lab not in labels:
                labels.append(lab)
    if judge_uncertain and "evaluator_uncertainty" not in labels:
        labels.append("evaluator_uncertainty")
    return labels
