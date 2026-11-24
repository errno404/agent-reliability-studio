"""Domain models shared by every evalcore module.

Design rules encoded here:
* Observable evidence only. There is deliberately no field for hidden reasoning.
* An execution error is never a quality failure (``SampleStatus``).
* Every assertion returns structured evidence, never a bare boolean.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SampleStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    EXECUTION_ERROR = "execution_error"
    INVALID = "invalid"
    SKIPPED = "skipped"


class Layer(StrEnum):
    """Scoring layers. Intentionally never collapsed into one weighted score."""

    OUTCOME = "outcome"
    TRAJECTORY = "trajectory"
    COMPONENT = "component"
    POLICY = "policy"
    DIAGNOSTIC = "diagnostic"  # never gates until its evaluator is calibrated


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0


class SpanRecord(BaseModel):
    """A persisted, already-redacted span (OTel-shaped)."""

    model_config = ConfigDict(extra="forbid")
    span_id: str
    parent_id: str | None = None
    trace_id: str = ""
    name: str
    kind: str  # agent | model | tool | retrieval | run
    start_ms: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"  # ok | error
    attributes: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Everything observable about one agent execution."""

    model_config = ConfigDict(extra="forbid")
    final_output: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    turns: int = 1
    steps: int = 0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    model: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    commands: dict[str, dict[str, Any]] = Field(default_factory=dict)  # name -> {exit_code, ...}
    workspace_files: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    spans: list[SpanRecord] = Field(default_factory=list)
    error: str | None = None  # set => execution error, not quality failure
    error_kind: str | None = None  # timeout | provider | adapter | crash
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def tool_names(self) -> list[str]:
        return [c.name for c in self.tool_calls]


class AssertionSpec(BaseModel):
    """A declarative assertion. Extra keys are the assertion's parameters."""

    model_config = ConfigDict(extra="allow")
    type: str
    layer: Layer = Layer.OUTCOME
    gating: bool = True
    severity: Severity = Severity.MEDIUM
    label: str | None = None  # optional taxonomy label override
    note: str | None = None

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class AssertionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    layer: Layer
    gating: bool
    passed: bool
    expected: Any = None
    actual: Any = None
    evidence: str = ""
    severity: Severity = Severity.MEDIUM
    invalid: bool = False  # spec itself is malformed
    skipped: bool = False  # evaluator could not run (e.g. no pricing)
    label: str | None = None


class SimulatedUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    persona: str
    style: str = "neutral"
    hidden_goal: str = ""
    max_turns: int = 4
    script: list[str] = Field(default_factory=list)  # scripted mode
    expected_goal_state: dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    category: str
    description: str = ""  # WHY this case exists
    input: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)
    fixture: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    assertions: list[AssertionSpec] = Field(default_factory=list)
    trajectory: dict[str, Any] = Field(default_factory=dict)
    budgets: dict[str, Any] = Field(default_factory=dict)
    rubric: dict[str, Any] = Field(default_factory=dict)
    severity: Severity = Severity.MEDIUM
    simulated_user: SimulatedUser | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    description: str = ""
    kind: str = "support"  # support | research | coding | redteam
    published: bool = False
    fixture_version: str = ""
    cases: list[Case]


class SampleResult(BaseModel):
    """The scored outcome of one (case, sample_index) execution."""

    model_config = ConfigDict(extra="forbid")
    case_id: str
    category: str
    sample_index: int
    status: SampleStatus
    assertions: list[AssertionResult] = Field(default_factory=list)
    result: AgentResult
    failure_labels: list[str] = Field(default_factory=list)
    judge: dict[str, Any] | None = None
    seed: int | None = None

    def layer_pass(self, layer: Layer) -> bool | None:
        """Pass/fail for one layer, or ``None`` if the layer has no gating assertions."""
        rel = [a for a in self.assertions if a.layer == layer and a.gating and not a.skipped]
        if not rel:
            return None
        return all(a.passed for a in rel)

    @property
    def counts_for_quality(self) -> bool:
        return self.status in (SampleStatus.PASSED, SampleStatus.FAILED)
