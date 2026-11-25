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
from .models import SampleResult

EVALUATOR_VERSION = "evalcore-1.0"  # a human-readable label ONLY; identity is evaluator_hash()

_EVALUATOR_FILES = (
    "assertions",
    "stats",
    "compare",
    "manifest",
    "runner",
    "summary",
    "judge",
    "calibration",
    "taxonomy",
    "trajectory",
    "dataset",
    "models",
)


def evaluator_hash() -> str:
    """Content hash of the evaluator implementation, so 'same evaluator' is proven by code, not by a label."""
    import hashlib
    from pathlib import Path

    h = hashlib.sha256()
    base = Path(__file__).parent
    for name in _EVALUATOR_FILES:
        h.update(name.encode())
        h.update((base / f"{name}.py").read_bytes())
    return h.hexdigest()[:16]


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
    execution_kind: str = "synthetic"  # "synthetic" (scripted demo agents) | "live" (real LLM)
    model_resolved: str = ""  # model actually reported by the provider ("" = unknown / not applicable)
    evaluator_hash: str = ""  # content hash of the evaluator implementation (see evaluator_hash())
    evaluator_config_hash: str = ""  # scoring configuration: assertion set, judge params, parsers
    rubric_hash: str = ""
    agent_config: dict[str, Any] = field(default_factory=dict)  # sanitized, behaviour-affecting agent settings
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def content_hash(self) -> str:
        d = self.to_dict()
        for volatile in ("run_id", "created_at", "git_commit", "git_dirty"):
            d.pop(volatile, None)
        return hash_obj(d, 16)


# ---------------------------------------------------------------- comparison intent
# Every comparison states WHAT is intentionally different; everything else must be controlled.
ALWAYS_CONTROLLED = (
    "dataset_name",
    "dataset_hash",
    "fixture_hash",
    "samples_per_case",
    "execution_kind",
    "model_provider",
    "simulated_user_model",
    "simulated_user_prompt_hash",
)
CONTROLLED_UNLESS_VARIED = {
    "model": ("model", "model_resolved", "model_params"),
    "tools": ("tool_schema_hash",),
    "evaluator": (
        "evaluator_hash",
        "evaluator_config_hash",
        "rubric_hash",
        "judge_backend",
        "judge_model",
        "judge_prompt_hash",
    ),
}
# intent -> the groups that MAY differ (all other groups must match)
INTENTS: dict[str, tuple[str, ...]] = {
    "prompt_change": (),
    "agent_change": (),
    "model_change": ("model",),
    "tool_change": ("tools",),
    "evaluator_change": ("evaluator",),
}
INTENT_LABEL = {
    "prompt_change": "agent prompt changed",
    "agent_change": "agent implementation changed",
    "model_change": "model changed",
    "tool_change": "tools changed",
    "evaluator_change": "evaluator changed",
}
DEFAULT_INTENT = "agent_change"
_CODES = {
    "dataset_hash": "dataset_mismatch",
    "fixture_hash": "fixture_mismatch",
    "judge_prompt_hash": "judge_changed",
    "judge_model": "judge_changed",
    "judge_backend": "judge_changed",
    "samples_per_case": "sample_count_mismatch",
    "model": "model_mismatch",
    "execution_kind": "execution_kind_mismatch",
    "evaluator_hash": "evaluator_changed",
}


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
    intent: str = DEFAULT_INTENT
    coverage: dict[str, Any] = field(default_factory=dict)

    @property
    def reasons(self) -> list[str]:
        return [f"{i.code}: {i.message}" for i in self.issues if i.fatal]

    @property
    def warnings(self) -> list[str]:
        return [f"{i.code}: {i.message}" for i in self.issues if not i.fatal]


def coverage_of(man: RunManifest, samples: list[SampleResult]) -> dict[str, Any]:
    """Required-observation coverage: every (case, sample_index) the manifest promised, by outcome."""
    want = {(c, i) for c in man.case_ids for i in range(man.samples_per_case)}
    got = {(s.case_id, s.sample_index): s for s in samples}
    missing = sorted(want - got.keys())
    bad = {"execution_error": 0, "invalid": 0, "skipped": 0}
    for k in want & got.keys():
        st = got[k].status.value
        if st in bad:
            bad[st] += 1
    n = max(1, len(want))
    return {
        "expected": len(want),
        "present": len(want & got.keys()),
        "missing": len(missing),
        **bad,
        "incomplete": len(missing) + sum(bad.values()),
        "incomplete_share": (len(missing) + sum(bad.values())) / n,
        "missing_examples": [f"{c}#{i}" for c, i in missing[:3]],
    }


def validate_pair(
    base: RunManifest,
    cand: RunManifest,
    base_samples: list[SampleResult],
    cand_samples: list[SampleResult],
    mode: str = "strict",
    base_complete: bool = True,
    cand_complete: bool = True,
    intent: str = DEFAULT_INTENT,
) -> ValidationReport:
    """Return validity of a baseline/candidate comparison for a stated INTENT.

    ``strict`` (release gating) requires every controlled field to match; fields the intent says may vary are reported
    as intended changes. ``exploratory`` downgrades provenance mismatches to warnings but still refuses structurally
    broken comparisons AND any synthetic-vs-live mix. Unknown intents are rejected.
    """
    issues: list[Issue] = []
    strict = mode == "strict"
    if intent not in INTENTS:
        return ValidationReport(
            False, [Issue("unknown_intent", f"intent must be one of {sorted(INTENTS)}")], mode, intent
        )
    if not base_complete:
        issues.append(Issue("incomplete_run", "baseline run did not complete"))
    if not cand_complete:
        issues.append(Issue("incomplete_run", "candidate run did not complete"))

    varied = {f for g in INTENTS[intent] for f in CONTROLLED_UNLESS_VARIED[g]}
    controlled = list(ALWAYS_CONTROLLED) + [
        f for fs in CONTROLLED_UNLESS_VARIED.values() for f in fs if f not in varied
    ]
    for f in controlled:
        a, b = getattr(base, f), getattr(cand, f)
        if a != b:
            always_fatal = f == "execution_kind"  # synthetic and live results are never comparable
            issues.append(
                Issue(
                    _CODES.get(f, f"{f}_mismatch"),
                    f"{f}: baseline={a!r} candidate={b!r} (controlled for intent '{intent}')",
                    fatal=strict or always_fatal,
                )
            )
    for f in sorted(varied):
        a, b = getattr(base, f), getattr(cand, f)
        if a != b:
            issues.append(
                Issue(
                    "intended_change", f"{f} differs as intended ({INTENT_LABEL[intent]}): {a!r} -> {b!r}", fatal=False
                )
            )
    if strict:
        for f in ("evaluator_hash",):
            if not getattr(base, f) or not getattr(cand, f):
                issues.append(Issue("evaluator_unknown", f"{f} is not recorded; evaluator identity cannot be proven"))

    if set(base.case_ids) != set(cand.case_ids):
        only_b, only_c = set(base.case_ids) - set(cand.case_ids), set(cand.case_ids) - set(base.case_ids)
        issues.append(Issue("case_set_mismatch", f"{len(only_b)} baseline-only, {len(only_c)} candidate-only cases"))
    if not (set(base.case_ids) & set(cand.case_ids)):
        issues.append(Issue("no_overlap", "no cases in common (empty comparison)"))

    cov: dict[str, Any] = {}
    for label, man, samples in (("baseline", base, base_samples), ("candidate", cand, cand_samples)):
        cov[label] = c = coverage_of(man, samples)
        if c["missing"]:
            issues.append(
                Issue(
                    "missing_samples",
                    f"{label}: {c['missing']} expected sample(s) absent (e.g. {c['missing_examples']})",
                )
            )
        stray = sorted({s.case_id for s in samples} - set(man.case_ids))
        if stray:
            issues.append(Issue("unexpected_samples", f"{label}: samples for cases not in the manifest: {stray[:3]}"))
        keys = [(s.case_id, s.sample_index) for s in samples]
        if len(keys) != len(set(keys)):
            issues.append(Issue("duplicate_samples", f"{label}: duplicate (case, sample_index) rows"))
        n_err = c["execution_error"]
        if n_err:
            issues.append(
                Issue(
                    "execution_errors",
                    f"{label}: {n_err}/{c['expected']} samples are execution errors "
                    "(reported separately; a release decision needs complete evidence)",
                    fatal=n_err / max(1, c["expected"]) > 0.2,
                )
            )
        if c["invalid"] or c["skipped"]:
            issues.append(
                Issue(
                    "unevaluable_samples",
                    f"{label}: {c['invalid']} invalid and {c['skipped']} skipped required samples",
                )
            )
        # sample-level metadata must agree with the manifest (alias drift / mixed provenance)
        observed = {s.result.model for s in samples if s.result.model and s.status.value != "execution_error"}
        if man.model_resolved and observed and observed != {man.model_resolved}:
            issues.append(
                Issue(
                    "model_alias_drift",
                    f"{label}: manifest resolved model {man.model_resolved!r} but samples report {sorted(observed)}",
                    fatal=True,
                )
            )
        kinds = {str(s.result.metadata.get("execution_kind", man.execution_kind)) for s in samples}
        if kinds - {man.execution_kind}:
            issues.append(
                Issue(
                    "execution_kind_mismatch",
                    f"{label}: samples report {sorted(kinds)} but manifest says {man.execution_kind}",
                )
            )
    if base.agent != cand.agent:
        issues.append(
            Issue("agent_mismatch", f"comparing different agents: {base.agent} vs {cand.agent}", fatal=strict)
        )
    return ValidationReport(not any(i.fatal for i in issues), issues, mode, intent, cov)
