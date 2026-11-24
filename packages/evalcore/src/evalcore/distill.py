"""Trace-to-eval distillation: trace -> suggested CANDIDATE case (never auto-promoted)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .models import AgentResult, Case


def distill_case(source: Case, result: AgentResult, run_id: str, sample_index: int,
                 observed_ok: bool) -> dict[str, Any]:
    """Suggest a regression case from an observed execution.

    Observed tool names/arguments become *proposed* assertions for a human to edit.
    Status is always ``candidate``; promotion requires review and a new dataset version.
    """
    asserts: list[dict[str, Any]] = []
    for t in result.tool_calls:
        if t.arguments:
            asserts.append({"type": "tool_arguments_match", "layer": "component", "name": t.name,
                            "arguments": t.arguments, "which": "any"})
        else:
            asserts.append({"type": "tool_called", "layer": "component", "name": t.name})
    if result.tool_calls:
        asserts.append({"type": "tool_sequence", "layer": "trajectory", "sequence": result.tool_names,
                        "mode": "subsequence"})
    if result.final_output:
        asserts.append({"type": "output_contains", "layer": "outcome", "value": result.final_output[:60],
                        "gating": False, "note": "placeholder: replace with the key fact a correct answer needs"})
    return {
        "id": f"candidate-{source.id}-{run_id[:8]}-{sample_index}",
        "title": f"Candidate from {source.id}",
        "category": source.category,
        "description": (f"Distilled from run {run_id} sample {sample_index} "
                        f"({'observed passing behaviour' if observed_ok else 'observed failing behaviour'}). "
                        "NEEDS HUMAN REVIEW before promotion."),
        "input": source.input, "fixture": source.fixture, "tags": [*source.tags, "distilled"],
        "assertions": asserts,
        "provenance": {"status": "candidate", "source_case": source.id, "run_id": run_id,
                       "sample_index": sample_index, "observed_ok": observed_ok,
                       "distilled_at": datetime.now(UTC).isoformat()},
    }
