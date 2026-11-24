"""Run manifests and fair-comparison validation.

A baseline/candidate pair is only comparable when critical provenance matches. Fields
that are *expected* to differ between baseline and candidate (agent version, prompt/code
hash, git commit, run id, timestamp) are excluded from the strict-match set.
"""

from __future__ import annotations

import platform
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from .hashing import hash_obj
from .models import SampleResult, SampleStatus

EVALUATOR_VERSION = "evalcore-1.0"


@dataclass
class RunManifest:
    run_id: str
    run_type: str  # "synthetic_demo" | "live" | "ci_gate"
    agent: str
    agent_version: str
    agent_hash: str = ""
    dataset_name: str = ""
    dataset_path: str = ""
    dataset_hash: str = ""
    fixture_hash: str = ""
    case_ids: list[str] = field(default_factory=list)
    samples_per_case: int = 1
    model_provider: str = ""
    model: str = ""
    model_params: dict[str, Any] = field(default_factory=dict)
    judge_backend: str = ""
    judge_model: str = ""
    judge_prompt_hash: str = ""
    simulated_user_model: str = ""
    simulated_user_prompt_hash: str = ""
    tool_schema_hash: str = ""
    git_commit: str = ""
    git_dirty: bool = False
    evaluator_version: str = EVALUATOR_VERSION
    python_version: str = field(default_factory=platform.python_version)
    package_version: str = "0.1.0"
    concurrency: int = 1
    seed: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def content_hash(self) -> str:
        d = self.to_dict()
        for volatile in ("run_id", "created_at", "git_commit", "git_dirty"):
            d.pop(volatile, None)
        return hash_obj(d, 16)


# fields that must be identical for a *strict* (CI-gating) comparison
STRICT_MATCH = (
    "dataset_name",
    "dataset_hash",
    "fixture_hash",
    "samples_per_case",
    "judge_backend",
    "judge_model",
    "judge_prompt_hash",
    "simulated_user_model",
    "simulated_user_prompt_hash",
    "evaluator_version",
    "model_provider",
    "model",
)


@dataclass
class Issue:
    code: str
    message: str
    fatal: bool = True


@dataclass
class ValidationReport:
    valid: bool
    issues: list[Issue]
    mode: str

    @property
    def reasons(self) -> list[str]:
        return [f"{i.code}: {i.message}" for i in self.issues if i.fatal]

    @property
    def warnings(self) -> list[str]:
        return [f"{i.code}: {i.message}" for i in self.issues if not i.fatal]


def validate_pair(
    base: RunManifest,
    cand: RunManifest,
    base_samples: list[SampleResult],
    cand_samples: list[SampleResult],
    mode: str = "strict",
    base_complete: bool = True,
    cand_complete: bool = True,
) -> ValidationReport:
    """Return validity of a baseline/candidate comparison.

    ``mode='strict'`` (CI gating) requires every STRICT_MATCH field to match.
    ``mode='exploratory'`` downgrades provenance mismatches to warnings but still refuses
    structurally broken comparisons (incomplete runs, no overlap, missing samples).
    """
    issues: list[Issue] = []
    strict = mode == "strict"
    if not base_complete:
        issues.append(Issue("incomplete_run", "baseline run did not complete"))
    if not cand_complete:
        issues.append(Issue("incomplete_run", "candidate run did not complete"))

    for f in STRICT_MATCH:
        a, b = getattr(base, f), getattr(cand, f)
        if a != b:
            code = {
                "dataset_hash": "dataset_mismatch",
                "fixture_hash": "fixture_mismatch",
                "judge_prompt_hash": "judge_changed",
                "judge_model": "judge_changed",
                "judge_backend": "judge_changed",
                "samples_per_case": "sample_count_mismatch",
                "model": "model_mismatch",
            }.get(f, f"{f}_mismatch")
            issues.append(Issue(code, f"{f}: baseline={a!r} candidate={b!r}", fatal=strict))

    if set(base.case_ids) != set(cand.case_ids):
        only_b, only_c = set(base.case_ids) - set(cand.case_ids), set(cand.case_ids) - set(base.case_ids)
        issues.append(Issue("case_set_mismatch", f"{len(only_b)} baseline-only, {len(only_c)} candidate-only cases"))

    def _by_case(samples: list[SampleResult]) -> dict[str, set[int]]:
        out: dict[str, set[int]] = {}
        for s in samples:
            out.setdefault(s.case_id, set()).add(s.sample_index)
        return out

    for label, man, samples in (("baseline", base, base_samples), ("candidate", cand, cand_samples)):
        got = _by_case(samples)
        want = set(range(man.samples_per_case))
        missing = [c for c in man.case_ids if got.get(c, set()) != want]
        if missing:
            issues.append(
                Issue(
                    "missing_samples",
                    f"{label}: {len(missing)} case(s) lack expected sample indexes (e.g. {missing[:3]})",
                )
            )
        keys = [(s.case_id, s.sample_index) for s in samples]
        if len(keys) != len(set(keys)):
            issues.append(Issue("duplicate_samples", f"{label}: duplicate (case, sample_index) rows"))
        n_err = sum(1 for s in samples if s.status == SampleStatus.EXECUTION_ERROR)
        if n_err:
            # execution errors are excluded from quality stats, but too many make comparison unreliable
            frac = n_err / max(1, len(samples))
            issues.append(
                Issue(
                    "execution_errors",
                    f"{label}: {n_err}/{len(samples)} samples are execution errors (excluded from quality metrics)",
                    fatal=frac > 0.2,
                )
            )
        n_inv = sum(1 for s in samples if s.status == SampleStatus.INVALID)
        if n_inv:
            issues.append(Issue("invalid_samples", f"{label}: {n_inv} sample(s) have invalid assertions"))

    if not (set(base.case_ids) & set(cand.case_ids)):
        issues.append(Issue("no_overlap", "no cases in common"))
    if base.agent != cand.agent:
        issues.append(
            Issue("agent_mismatch", f"comparing different agents: {base.agent} vs {cand.agent}", fatal=strict)
        )
    return ValidationReport(not any(i.fatal for i in issues), issues, mode)
