"""LLM-as-judge: narrow dimensions, strict structured output, safe retry.

The offline ``HeuristicJudge`` is a deterministic, clearly-labelled stand-in so the whole
product works with zero API keys; it is calibrated like any other judge (and may fail).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .hashing import sha256_hex

DIMENSIONS = ("factual_correctness", "instruction_satisfaction", "groundedness", "policy_adherence")

JUDGE_PROMPT_TEMPLATE = """You are a strict evaluator scoring ONE narrow dimension: {dimension}.
Judge only the observable candidate output against the rubric. Do not reward length or tone.
Respond with a single JSON object and nothing else:
{{"passed": bool, "score": number 0..1, "label": "pass"|"fail", "rationale": str, "evidence": [str]}}

RUBRIC ({rubric_version}):
{rubric}

INPUT:
{input}

CANDIDATE OUTPUT:
{output}
"""


class JudgeVerdict(BaseModel):
    """Strictly validated judge output."""

    model_config = ConfigDict(extra="forbid")
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    label: str
    rationale: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> JudgeVerdict:
        if self.label not in ("pass", "fail"):
            raise ValueError("label must be 'pass' or 'fail'")
        if (self.label == "pass") != self.passed:
            raise ValueError("label and passed disagree")
        return self


class MalformedJudgeOutput(Exception):
    pass


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_verdict(raw: str) -> JudgeVerdict:
    text = _FENCE.sub("", raw.strip()).strip()
    try:
        return JudgeVerdict.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise MalformedJudgeOutput(str(exc)[:300]) from exc


class JudgeBackend(Protocol):
    name: str  # e.g. "heuristic", "litellm"
    model: str

    def complete(self, prompt: str) -> str: ...


@dataclass
class JudgeConfig:
    backend: str
    model: str
    dimension: str = "factual_correctness"
    rubric_version: str = "r1"
    prompt_template: str = JUDGE_PROMPT_TEMPLATE
    max_retries: int = 2
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        return sha256_hex(self.prompt_template + "|" + self.dimension + "|" + self.rubric_version)[:16]


@dataclass
class JudgeOutcome:
    verdict: JudgeVerdict | None
    attempts: int
    error: str | None = None  # judge failure is NOT an agent failure

    @property
    def ok(self) -> bool:
        return self.verdict is not None


class Judge:
    def __init__(self, backend: JudgeBackend, config: JudgeConfig):
        self.backend, self.config = backend, config

    def render(self, rubric: str, input_text: str, output: str) -> str:
        return self.config.prompt_template.format(
            dimension=self.config.dimension, rubric=rubric, input=input_text, output=output,
            rubric_version=self.config.rubric_version)

    def evaluate(self, rubric: str, input_text: str, output: str) -> JudgeOutcome:
        prompt = self.render(rubric, input_text, output)
        last = ""
        for attempt in range(1, self.config.max_retries + 2):
            try:
                raw = self.backend.complete(prompt if attempt == 1 else
                                            prompt + f"\n\nYour previous reply was invalid ({last}). "
                                            "Reply with ONLY the JSON object.")
            except Exception as exc:  # provider failure
                return JudgeOutcome(None, attempt, f"provider_error: {type(exc).__name__}: {exc}"[:300])
            try:
                return JudgeOutcome(parse_verdict(raw), attempt)
            except MalformedJudgeOutput as exc:
                last = str(exc)
        return JudgeOutcome(None, self.config.max_retries + 1, f"malformed_output: {last}")


_WORD = re.compile(r"[a-z0-9$.%']+")


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


class HeuristicJudge:
    """Deterministic offline judge: rubric-keyword coverage minus forbidden-claim hits.

    Rubric text format understood: lines ``MUST: <phrase>`` and ``MUST_NOT: <phrase>``.
    It is intentionally simple; calibration is what tells us whether it is trustworthy.
    """

    name = "heuristic"

    def __init__(self, model: str = "keyword-v1", strictness: float = 0.6):
        self.model, self.strictness = model, strictness

    def complete(self, prompt: str) -> str:
        rubric = prompt.split("RUBRIC", 1)[1].split("INPUT:", 1)[0]
        output = prompt.rsplit("CANDIDATE OUTPUT:", 1)[1].lower()
        musts = re.findall(r"MUST:\s*(.+)", rubric)
        must_nots = re.findall(r"MUST_NOT:\s*(.+)", rubric)
        hit = [m for m in musts if m.strip().lower() in output or _tokens(m) <= _tokens(output)]
        bad = [m for m in must_nots if m.strip().lower() in output]
        score = (len(hit) / len(musts)) if musts else 0.5
        score = 0.0 if bad else score
        passed = (not bad) and score >= self.strictness
        return json.dumps({
            "passed": passed, "score": round(score, 3), "label": "pass" if passed else "fail",
            "rationale": f"{len(hit)}/{len(musts)} required points present; {len(bad)} forbidden claims",
            "evidence": [f"present: {h.strip()}" for h in hit] + [f"forbidden: {b.strip()}" for b in bad]})


class ScriptedBackend:
    """Test double returning queued raw strings (used to test malformed-output retry)."""

    name = "scripted"

    def __init__(self, replies: list[str | Exception], model: str = "scripted-1"):
        self.replies, self.model = list(replies), model

    def complete(self, prompt: str) -> str:
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class LiteLLMBackend:
    """Optional provider-backed judge. Requires the ``litellm`` extra and provider credentials."""

    name = "litellm"

    def __init__(self, model: str, temperature: float = 0.0, completion: Callable[..., Any] | None = None):
        self.model, self.temperature = model, temperature
        self._completion = completion

    def complete(self, prompt: str) -> str:
        fn = self._completion
        if fn is None:
            try:
                import litellm  # pyright: ignore[reportMissingImports]
            except ImportError as exc:
                raise RuntimeError("litellm not installed; install evalcore[litellm]") from exc
            fn = litellm.completion
        resp = fn(model=self.model, temperature=self.temperature,
                  messages=[{"role": "user", "content": prompt}])
        return str(resp.choices[0].message.content)
