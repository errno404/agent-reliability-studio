"""Sync file-based catalog (agents, datasets, calibration sets, judges) into the database.

Published dataset versions are FROZEN: re-syncing a published version whose content hash differs
is refused (never silently mutate evidence)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml
from evalcore import load_and_validate
from evalcore.calibration import judge_identity
from evalcore.hashing import hash_obj
from evalcore.judge import JudgeConfig
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import REPO_ROOT
from ..models import (
    Agent,
    AgentVersion,
    CalibrationItem,
    CalibrationSet,
    Dataset,
    DatasetVersion,
    EvalCase,
)
from ..models import (
    JudgeConfig as JudgeRow,
)


class FrozenDatasetError(RuntimeError):
    pass


def git_info() -> tuple[str, bool]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
            ).stdout.strip()
        )
        return sha or "unknown", dirty
    except Exception:
        return "unknown", False


def fixture_hash_for(kind: str) -> str:
    from fixture_web import load_corpus

    parts: dict[str, str] = {}
    if kind in ("support", "redteam"):
        parts["support_world"] = hash_obj(yaml.safe_load((REPO_ROOT / "fixtures/support/world.yaml").read_text()), 16)
    if kind in ("research", "redteam"):
        parts["web"] = load_corpus().content_hash
    if kind == "coding":
        parts["code"] = hash_obj(
            sorted(
                (p.relative_to(REPO_ROOT / "fixtures/code").as_posix(), p.read_text())
                for p in (REPO_ROOT / "fixtures/code").rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            ),
            16,
        )
    return hash_obj(parts, 16)


def sync_agent_version(s: Session, spec: str, role: str = "", notes: str = "") -> AgentVersion:
    from demo_agents import agent_info

    info = agent_info(spec)
    agent = s.scalar(select(Agent).where(Agent.name == info["agent"]))
    if agent is None:
        agent = Agent(
            name=info["agent"], description=f"Synthetic reference {info['agent']} system (scripted + seeded faults)"
        )
        s.add(agent)
        s.flush()
    av = s.scalar(
        select(AgentVersion).where(AgentVersion.agent_id == agent.id, AgentVersion.version == info["version"])
    )
    sha, _ = git_info()
    if av is None:
        av = AgentVersion(agent_id=agent.id, version=info["version"], role=role, notes=notes)
        s.add(av)
    av.agent_hash, av.prompt_hash = info["agent_hash"], info["prompt_hash"]
    av.tool_schema_hash, av.model, av.git_commit = info["tool_schema_hash"], info["model"], sha
    if role:
        av.role = role
    if notes:
        av.notes = notes
    s.flush()
    return av


def sync_dataset(s: Session, path: str | Path) -> DatasetVersion:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    ds, h = load_and_validate(p)
    d = s.scalar(select(Dataset).where(Dataset.name == ds.name))
    if d is None:
        d = Dataset(name=ds.name, kind=ds.kind, description=ds.description)
        s.add(d)
        s.flush()
    dv = s.scalar(select(DatasetVersion).where(DatasetVersion.dataset_id == d.id, DatasetVersion.version == ds.version))
    rel = p.relative_to(REPO_ROOT).as_posix() if p.is_relative_to(REPO_ROOT) else str(p)
    if dv is not None:
        if dv.hash != h and dv.published:
            raise FrozenDatasetError(
                f"{ds.name}:{ds.version} is published (hash {dv.hash}) but the file now hashes to {h}. "
                "Published datasets are frozen; create a new version instead."
            )
        if dv.hash == h:
            return dv
        for c in list(s.scalars(select(EvalCase).where(EvalCase.dataset_version_id == dv.id))):
            s.delete(c)
        s.flush()
    else:
        dv = DatasetVersion(dataset_id=d.id, version=ds.version, hash=h)
        s.add(dv)
    dv.hash, dv.fixture_version, dv.published = h, ds.fixture_version, ds.published
    dv.fixture_hash, dv.case_count, dv.source_path, dv.description = (
        fixture_hash_for(ds.kind),
        len(ds.cases),
        rel,
        ds.description,
    )
    s.flush()
    for c in ds.cases:
        s.add(
            EvalCase(
                dataset_version_id=dv.id,
                case_id=c.id,
                title=c.title,
                category=c.category,
                severity=c.severity.value,
                description=c.description,
                tags=list(c.tags),
                definition=c.model_dump(mode="json"),
            )
        )
    s.flush()
    return dv


def sync_calibration_set(s: Session, path: str | Path) -> CalibrationSet:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    raw: dict[str, Any] = yaml.safe_load(p.read_text())
    h = hash_obj(raw, 16)
    cs = s.scalar(
        select(CalibrationSet).where(CalibrationSet.name == raw["name"], CalibrationSet.version == raw["version"])
    )
    if cs is not None:
        if cs.hash != h:
            raise FrozenDatasetError(
                f"calibration set {raw['name']}:{raw['version']} changed on disk; bump the version"
            )
        return cs
    cs = CalibrationSet(
        name=raw["name"],
        version=raw["version"],
        hash=h,
        dimension=raw.get("dimension", "factual_correctness"),
        description=raw.get("description", ""),
        n_items=len(raw["items"]),
    )
    s.add(cs)
    s.flush()
    for it in raw["items"]:
        s.add(
            CalibrationItem(
                set_id=cs.id,
                item_id=it["id"],
                input=it["input"],
                candidate_output=it["candidate_output"],
                rubric=it["rubric"],
                reference_label=it["reference_label"] == "pass",
                label_source=it["label_source"],
                notes=it.get("notes", ""),
            )
        )
    s.flush()
    return cs


def sync_judge(
    s: Session, name: str, backend: str, model: str, cfg: JudgeConfig, params: dict[str, Any], description: str = ""
) -> JudgeRow:
    ident = judge_identity(backend, model, cfg.prompt_hash)
    j = s.scalar(select(JudgeRow).where(JudgeRow.identity == ident))
    if j is None:
        j = JudgeRow(
            identity=ident,
            name=name,
            backend=backend,
            model=model,
            prompt_hash=cfg.prompt_hash,
            dimension=cfg.dimension,
            rubric_version=cfg.rubric_version,
            params=params,
            description=description,
        )
        s.add(j)
        s.flush()
    return j
