# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# (inspect-ai is an optional dependency, and this folder shares its package name)
"""Export our research dataset to Inspect AI.

``research_cases_as_samples`` is dependency-free (plain dicts shaped like Inspect ``Sample`` kwargs).
``research_task`` needs ``inspect-ai`` installed and runs OUR reference research agent as the Inspect solver, so
the same cases can be scored by Inspect's own scorers and then re-ingested with :func:`ingest.ingest_inspect_log`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from evalcore import load_and_validate

ROOT = Path(__file__).resolve().parents[2]


def research_cases_as_samples(path: str | Path | None = None) -> list[dict[str, Any]]:
    """One Inspect-style sample per case. ``target`` = the first required answer fragment (outcome assertion)."""
    ds, h = load_and_validate(path or ROOT / "datasets/research/v1.yaml")
    out = []
    for c in ds.cases:
        want = next(
            (
                a.params.get("values")
                for a in c.assertions
                if a.type == "output_contains" and a.layer.value == "outcome"
            ),
            None,
        )
        out.append(
            {
                "id": c.id,
                "input": c.input,
                "target": list(want or []),
                "metadata": {"category": c.category, "dataset_hash": h, "executable": not c.fixture.get("mcp_down")},
            }
        )
    return out


def research_task(version: str = "v2", limit: int | None = None) -> Any:
    """Build an ``inspect_ai.Task`` whose solver is our research agent (no model call is made)."""
    from demo_agents import get_adapter
    from evalcore.models import Case
    from evalcore.runner import RunContext
    from inspect_ai import Task
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.scorer import Score, Target, accuracy, scorer
    from inspect_ai.solver import TaskState, solver

    adapter = get_adapter(f"research:{version}")
    samples = [s for s in research_cases_as_samples() if s["metadata"]["executable"]]
    if limit:
        samples = samples[:limit]

    @solver
    def our_research_agent():  # type: ignore[no-untyped-def]
        async def solve(state: TaskState, generate: Any) -> TaskState:
            case = Case(
                id=str(state.sample_id),
                title="inspect",
                category="research",
                description="from inspect",
                input=state.input_text,
            )
            # our agents are synchronous (and open their own MCP event loop), so run them off Inspect's running loop
            res = await asyncio.to_thread(
                adapter.run, case, RunContext(run_id="inspect", sample_index=max(state.epoch - 1, 0), seed=1)
            )
            state.output.completion = res.final_output
            state.metadata["tool_sequence"] = res.tool_names
            return state

        return solve

    @scorer(metrics=[accuracy()])
    def contains_all():  # type: ignore[no-untyped-def]
        async def score(state: TaskState, target: Target) -> Score:
            frag = list(target)
            ok = bool(frag) and all(f.lower() in state.output.completion.lower() for f in frag)
            return Score(value="C" if ok else "I", answer=state.output.completion[:200], explanation=f"needs {frag}")

        return score

    ds = MemoryDataset(
        [Sample(id=s["id"], input=s["input"], target=s["target"], metadata=s["metadata"]) for s in samples]
    )
    return Task(dataset=ds, solver=our_research_agent(), scorer=contains_all(), name=f"ars-research-{version}")
