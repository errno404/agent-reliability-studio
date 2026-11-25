"""Typed API response models (drive the OpenAPI spec and the generated frontend types)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Meta(Out):
    name: str
    version: str
    demo_mode: bool
    environment: str
    synthetic_notice: str
    semconv: str
    evaluator_version: str


class Page(Out):
    page: int
    page_size: int
    total: int


class AgentVersionOut(Out):
    id: int
    agent: str
    version: str
    role: str
    agent_hash: str
    prompt_hash: str
    tool_schema_hash: str
    model: str
    git_commit: str
    frozen: bool
    notes: str


class DatasetVersionOut(Out):
    id: int
    dataset: str
    kind: str
    version: str
    hash: str
    fixture_version: str
    fixture_hash: str
    published: bool
    case_count: int
    source_path: str
    description: str
    categories: dict[str, int] = {}


class CaseOut(Out):
    case_id: str
    title: str
    category: str
    severity: str
    description: str
    tags: list[str]
    definition: dict[str, Any]


class DatasetDetail(DatasetVersionOut):
    cases: list[CaseOut]


class RunOut(Out):
    execution_kind: str
    id: str
    name: str
    run_type: str
    status: str
    agent: str
    agent_version: str
    model: str
    dataset: str
    dataset_version: str
    dataset_hash: str
    samples_per_case: int
    seed: int
    judge: str | None
    judge_admitted: bool
    git_commit: str
    pass_rate: float | None
    pass_ci: list[float] | None
    n_cases: int
    n_samples: int
    cost_usd: float | None
    cost_label: str
    p95_latency_ms: float
    progress_done: int
    progress_total: int
    is_synthetic: bool
    created_at: datetime
    error: str | None


class RunDetail(RunOut):
    manifest: dict[str, Any]
    summary: dict[str, Any]
    agent_hash: str
    prompt_hash: str
    tool_schema_hash: str
    clusters: list[dict[str, Any]]


class RunList(Page):
    items: list[RunOut]


class SampleOut(Out):
    id: int
    run_id: str
    case_id: str
    category: str
    sample_index: int
    status: str
    error_kind: str | None
    tool_sequence: list[str]
    latency_ms: float
    total_tokens: int
    cost_usd: float | None
    failure_labels: list[str]
    trace_id: str
    final_output_preview: str


class SampleList(Page):
    items: list[SampleOut]


class AssertionOut(Out):
    name: str
    type: str
    layer: str
    gating: bool
    passed: bool
    skipped: bool
    invalid: bool
    severity: str
    expected: Any = None
    actual: Any = None
    evidence: str
    label: str | None = None


class SampleDetail(SampleOut):
    input_text: str
    final_output: str
    result: dict[str, Any]
    judge: dict[str, Any] | None
    assertions: list[AssertionOut]
    status_explanation: str


class SpanOut(Out):
    span_id: str
    parent_id: str | None
    name: str
    kind: str
    start_ms: float
    duration_ms: float
    status: str
    attributes: dict[str, Any]


class TraceOut(Out):
    sample_id: int
    trace_id: str
    case_id: str
    run_id: str
    trajectory: list[str]
    total_ms: float
    spans: list[SpanOut]


class ComparisonOut(Out):
    id: int
    name: str
    baseline_run_id: str
    candidate_run_id: str
    baseline_label: str
    candidate_label: str
    mode: str
    intent: str
    policy_name: str
    policy: dict[str, Any]
    decision: str
    valid: bool
    explanation: str
    delta: float | None
    ci_low: float | None
    ci_high: float | None
    margin: float | None
    n_common_cases: int
    gate_verdict: str | None
    created_at: datetime


class ComparisonDetail(ComparisonOut):
    validity: dict[str, Any]
    result: dict[str, Any]
    baseline: RunOut
    candidate: RunOut


class CaseComparison(Out):
    case_id: str
    category: str
    description: str
    expected_assertions: list[dict[str, Any]]
    baseline: list[SampleDetail]
    candidate: list[SampleDetail]
    diff: dict[str, Any]


class GateOut(Out):
    id: int
    comparison_id: int
    comparison_name: str
    verdict: str
    reasons: list[str]
    judge_ok: bool
    conservative: bool
    decision: str
    valid: bool
    explanation: str
    policy_name: str
    margin: float | None
    ci_low: float | None
    ci_high: float | None
    delta: float | None
    changed_cases: int
    baseline_run_id: str
    candidate_run_id: str
    created_at: datetime


class JudgeOut(Out):
    id: int
    name: str
    backend: str
    model: str
    prompt_hash: str
    identity: str
    dimension: str
    rubric_version: str
    status: str  # calibrated | not_calibrated
    status_label: str
    admitted: bool
    latest: dict[str, Any] | None
    history: list[dict[str, Any]]


class BlindItem(Out):
    """What an annotator sees. Deliberately has NO reference label, judge verdict, source or notes."""

    item_id: str
    input: str
    candidate_output: str
    rubric: dict[str, Any]


class AnnotationIn(BaseModel):
    set_name: str = "calibration"
    item_id: str = Field(max_length=48)
    annotator: str = Field(pattern=r"^[A-Za-z0-9_.-]{2,40}$")
    label: bool | None  # None = skip
    note: str = Field(default="", max_length=500)


class AdjudicationIn(BaseModel):
    set_name: str = "calibration"
    item_id: str = Field(max_length=48)
    adjudicator: str = Field(pattern=r"^[A-Za-z0-9_.-]{2,40}$")
    label: bool
    note: str = Field(default="", max_length=500)


class RunCreate(BaseModel):
    agent: str  # "support:v1"
    dataset: str  # "support:v1"
    samples: int = 1
    seed: int = 0
    name: str | None = None


class CompareCreate(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    mode: str = "strict"
    policy: str = "production"
