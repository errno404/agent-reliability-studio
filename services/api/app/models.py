"""Normalized schema. JSON columns hold only genuinely free-form payloads (attributes, definitions)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Json = JSON().with_variant(JSONB(), "postgresql")


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: Json, list[Any]: Json}


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    versions: Mapped[list[AgentVersion]] = relationship(back_populates="agent")


class AgentVersion(Base):
    """A pinned system under test. Frozen versions are never edited (see PINS.md)."""

    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(32), default="")  # baseline | candidate
    agent_hash: Mapped[str] = mapped_column(String(64), default="")
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    tool_schema_hash: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    git_commit: Mapped[str] = mapped_column(String(64), default="")
    frozen: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    agent: Mapped[Agent] = relationship(back_populates="versions")


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    version: Mapped[str] = mapped_column(String(32))
    hash: Mapped[str] = mapped_column(String(32), index=True)
    fixture_version: Mapped[str] = mapped_column(String(64), default="")
    fixture_hash: Mapped[str] = mapped_column(String(64), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    source_path: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    dataset: Mapped[Dataset] = relationship()


class EvalCase(Base):
    __tablename__ = "eval_cases"
    __table_args__ = (UniqueConstraint("dataset_version_id", "case_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(96))
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[Any]] = mapped_column(Json, default=list)
    definition: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class JudgeConfig(Base):
    """Identity = (backend, model, prompt_hash). Any change requires a new calibration."""

    __tablename__ = "judge_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    identity: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(96))
    backend: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    prompt_hash: Mapped[str] = mapped_column(String(32))
    dimension: Mapped[str] = mapped_column(String(48), default="factual_correctness")
    rubric_version: Mapped[str] = mapped_column(String(16), default="r1")
    params: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    description: Mapped[str] = mapped_column(Text, default="")


class CalibrationSet(Base):
    __tablename__ = "calibration_sets"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    hash: Mapped[str] = mapped_column(String(32))
    dimension: Mapped[str] = mapped_column(String(48), default="factual_correctness")
    description: Mapped[str] = mapped_column(Text, default="")
    n_items: Mapped[int] = mapped_column(Integer, default=0)


class CalibrationItem(Base):
    __tablename__ = "calibration_items"
    __table_args__ = (UniqueConstraint("set_id", "item_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("calibration_sets.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(48))
    input: Mapped[str] = mapped_column(Text)
    candidate_output: Mapped[str] = mapped_column(Text)
    rubric: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    reference_label: Mapped[bool] = mapped_column(Boolean)
    label_source: Mapped[str] = mapped_column(String(24))  # human | adjudicated | synthetic_fixture
    notes: Mapped[str] = mapped_column(Text, default="")


class CalibrationRun(Base):
    __tablename__ = "calibration_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    judge_config_id: Mapped[int] = mapped_column(ForeignKey("judge_configs.id"), index=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("calibration_sets.id"))
    n_items_used: Mapped[int] = mapped_column(Integer)
    policy: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    predictions: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)  # item_id -> predicted pass
    admitted: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[list[Any]] = mapped_column(Json, default=list)
    reference_sources: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    judge: Mapped[JudgeConfig] = relationship()


class HumanAnnotation(Base):
    __tablename__ = "human_annotations"
    __table_args__ = (UniqueConstraint("item_pk", "annotator"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    item_pk: Mapped[int] = mapped_column(ForeignKey("calibration_items.id"), index=True)
    annotator: Mapped[str] = mapped_column(String(64))
    label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # NULL = skipped
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(24), default="human")  # human | synthetic_demo
    adjudicated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_agent_version_created", "agent_version_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    run_type: Mapped[str] = mapped_column(String(24), default="synthetic_demo")  # synthetic_demo | live | ci_gate
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    agent_version_id: Mapped[int] = mapped_column(ForeignKey("agent_versions.id"))
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    judge_config_id: Mapped[int | None] = mapped_column(ForeignKey("judge_configs.id"), nullable=True)
    judge_admitted: Mapped[bool] = mapped_column(Boolean, default=False)
    samples_per_case: Mapped[int] = mapped_column(Integer, default=1)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    manifest: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    manifest_hash: Mapped[str] = mapped_column(String(32), default="")
    summary: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_version: Mapped[AgentVersion] = relationship()
    dataset_version: Mapped[DatasetVersion] = relationship()
    judge: Mapped[JudgeConfig | None] = relationship()


class RunExecution(Base):
    """One attempt to execute a run. Also the job queue (claimed with an atomic UPDATE)."""

    __tablename__ = "run_executions"
    __table_args__ = (Index("ix_exec_status", "status", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|succeeded|failed
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str] = mapped_column(String(64), default="")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Sample(Base):
    __tablename__ = "samples"
    __table_args__ = (
        UniqueConstraint("run_id", "case_id", "sample_index"),
        Index("ix_samples_run_status", "run_id", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(96), index=True)
    category: Mapped[str] = mapped_column(String(64))
    sample_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    error_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    input_text: Mapped[str] = mapped_column(Text, default="")
    final_output: Mapped[str] = mapped_column(Text, default="")
    tool_sequence: Mapped[list[Any]] = mapped_column(Json, default=list)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=1)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)  # AgentResult without spans (redacted)
    judge: Mapped[dict[str, Any] | None] = mapped_column(Json, nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(40), default="", index=True)
    assertions: Mapped[list[AssertionResultRow]] = relationship(back_populates="sample", cascade="all, delete-orphan")
    spans: Mapped[list[SpanRow]] = relationship(back_populates="sample", cascade="all, delete-orphan")
    labels: Mapped[list[FailureLabel]] = relationship(back_populates="sample", cascade="all, delete-orphan")


class SpanRow(Base):
    __tablename__ = "spans"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    trace_id: Mapped[str] = mapped_column(String(40), index=True)
    span_id: Mapped[str] = mapped_column(String(24))
    parent_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))
    start_ms: Mapped[float] = mapped_column(Float)
    duration_ms: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8), default="ok")
    attributes: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    sample: Mapped[Sample] = relationship(back_populates="spans")


class AssertionResultRow(Base):
    __tablename__ = "assertion_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    name: Mapped[str] = mapped_column(String(96))
    type: Mapped[str] = mapped_column(String(48))
    layer: Mapped[str] = mapped_column(String(16))
    gating: Mapped[bool] = mapped_column(Boolean)
    passed: Mapped[bool] = mapped_column(Boolean)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    invalid: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    expected: Mapped[Any] = mapped_column(Json, nullable=True)
    actual: Mapped[Any] = mapped_column(Json, nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    label: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sample: Mapped[Sample] = relationship(back_populates="assertions")


class FailureLabel(Base):
    __tablename__ = "failure_labels"
    __table_args__ = (Index("ix_failure_labels_label", "label", "run_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    label: Mapped[str] = mapped_column(String(48))
    sample: Mapped[Sample] = relationship(back_populates="labels")


class Comparison(Base):
    __tablename__ = "comparisons"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    baseline_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    candidate_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16), default="strict")
    policy_name: Mapped[str] = mapped_column(String(32), default="production")
    policy: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    valid: Mapped[bool] = mapped_column(Boolean)
    validity: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    baseline_run: Mapped[Run] = relationship(foreign_keys=[baseline_run_id])
    candidate_run: Mapped[Run] = relationship(foreign_keys=[candidate_run_id])


class FailureCluster(Base):
    __tablename__ = "failure_clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    label: Mapped[str] = mapped_column(String(48), index=True)
    count: Mapped[int] = mapped_column(Integer)
    pct_of_failures: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    categories: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    example_sample_ids: Mapped[list[Any]] = mapped_column(Json, default=list)
    source: Mapped[str] = mapped_column(String(16), default="deterministic")  # deterministic | llm (descriptive only)
    summary: Mapped[str] = mapped_column(Text, default="")


class CiGateDecision(Base):
    __tablename__ = "ci_gate_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(ForeignKey("comparisons.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(8))  # pass | fail
    reasons: Mapped[list[Any]] = mapped_column(Json, default=list)
    judge_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    conservative: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    comparison: Mapped[Comparison] = relationship()


class DistilledCandidate(Base):
    """Trace-to-eval workflow: trace -> suggested case -> human review -> approved dataset version."""

    __tablename__ = "distilled_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    case: Mapped[dict[str, Any]] = mapped_column(Json)
    status: Mapped[str] = mapped_column(String(16), default="candidate")  # candidate | approved | rejected
    reviewer: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
