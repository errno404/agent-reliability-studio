"""Dataset loading, validation and hashing.

The dataset hash covers every field that defines the evidence: case definitions,
fixtures, expected state (assertions), rubric, required/forbidden tools and the
fixture-corpus version. Editing any of them changes the hash, so a published
dataset can never be silently mutated.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .assertions import ASSERTION_TYPES
from .hashing import hash_obj
from .models import Case, Dataset

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class DatasetError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def load_dataset(path: str | Path) -> Dataset:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DatasetError([f"{p}: top level must be a mapping"])
    try:
        return Dataset.model_validate(raw)
    except ValidationError as exc:
        raise DatasetError([f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]) from exc


def case_hash_payload(case: Case) -> dict[str, Any]:
    d = case.model_dump(mode="json")
    d.pop("provenance", None)  # provenance explains origin; it is not evidence
    return d


def dataset_hash(ds: Dataset) -> str:
    payload = {
        "name": ds.name,
        "version": ds.version,
        "kind": ds.kind,
        "fixture_version": ds.fixture_version,
        "cases": sorted((case_hash_payload(c) for c in ds.cases), key=lambda c: c["id"]),
    }
    return hash_obj(payload, 16)


def validate_dataset(ds: Dataset) -> list[str]:
    """Return a list of human-readable problems (empty list == valid)."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in ds.cases:
        if c.id in seen:
            problems.append(f"duplicate case id: {c.id}")
        seen.add(c.id)
        if not _ID_RE.match(c.id):
            problems.append(f"{c.id}: id must match {_ID_RE.pattern}")
        if not c.description.strip():
            problems.append(f"{c.id}: description (why this case exists) is required")
        if not c.input and not c.messages and not c.simulated_user:
            problems.append(f"{c.id}: needs input, messages or simulated_user")
        if not any(a.gating for a in c.assertions):
            problems.append(f"{c.id}: needs at least one gating assertion")
        for a in c.assertions:
            if a.type not in ASSERTION_TYPES:
                problems.append(f"{c.id}: unknown assertion type '{a.type}'")
    if not ds.cases:
        problems.append("dataset has no cases")
    return problems


def load_and_validate(path: str | Path) -> tuple[Dataset, str]:
    ds = load_dataset(path)
    problems = validate_dataset(ds)
    if problems:
        raise DatasetError(problems)
    return ds, dataset_hash(ds)
