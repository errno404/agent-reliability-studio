"""Deterministic corpus + search. No network, no clock, no randomness."""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CORPUS = Path(
    os.environ.get("FIXTURE_CORPUS") or Path(__file__).resolve().parents[3] / "fixtures" / "web" / "corpus-v1.yaml"
)
_TOKEN = re.compile(r"[a-z0-9$.%,]+")
_STOP = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "and",
        "or",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "was",
        "were",
        "be",
        "by",
        "with",
        "at",
        "from",
        "as",
        "it",
        "its",
        "this",
        "that",
        "how",
        "what",
        "which",
        "who",
        "when",
        "where",
        "many",
        "much",
        "does",
        "do",
        "did",
    ]
)


def tokens(text: str) -> list[str]:
    return [t.strip(".,") for t in _TOKEN.findall(text.lower()) if t.strip(".,") and t.strip(".,") not in _STOP]


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    published: str
    snippet: str
    text: str
    authority: str = "low"  # ground truth; never returned to agents
    status: int = 200
    tags: tuple[str, ...] = ()


@dataclass
class FixtureWeb:
    version: str
    pages: dict[str, Page]
    contexts: dict[str, str]
    content_hash: str = ""
    _idx: dict[str, Counter[str]] = field(default_factory=dict, repr=False)
    _df: Counter[str] = field(default_factory=Counter, repr=False)

    def __post_init__(self) -> None:
        for url, p in self.pages.items():
            self._idx[url] = Counter(tokens(p.title) * 3 + tokens(p.snippet) * 2 + tokens(p.text))
            for t in set(self._idx[url]):
                self._df[t] += 1

    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        """BM25-lite over title/snippet/text. Same query -> same ranking, always."""
        qt = tokens(query)
        n = len(self.pages)
        scored: list[tuple[float, str]] = []
        for url, tf in self._idx.items():
            s = 0.0
            for t in qt:
                if t in tf:
                    idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                    s += idf * (tf[t] * 2.2) / (tf[t] + 1.2)
            if s > 0:
                scored.append((s, url))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [
            {
                "url": u,
                "title": self.pages[u].title,
                "snippet": self.pages[u].snippet,
                "published": self.pages[u].published,
            }
            for _, u in scored[:limit]
        ]

    def fetch(self, url: str) -> dict[str, Any]:
        """Return page text, or an explicit error (404/403/410 or unknown URL)."""
        p = self.pages.get(url)
        if p is None:
            return {"ok": False, "status": 404, "url": url, "error": "not found (URL is not in the corpus)"}
        if p.status != 200:
            reason = {404: "not found", 403: "forbidden (subscribers only)", 410: "gone"}.get(p.status, "error")
            return {"ok": False, "status": p.status, "url": url, "error": reason}
        return {"ok": True, "status": 200, "url": url, "title": p.title, "published": p.published, "text": p.text}

    def read_context(self, name: str) -> dict[str, Any]:
        if name not in self.contexts:
            return {"ok": False, "error": f"unknown context '{name}'", "available": sorted(self.contexts)}
        return {"ok": True, "name": name, "text": self.contexts[name]}


def load_corpus(path: str | Path | None = None) -> FixtureWeb:
    p = Path(path) if path else DEFAULT_CORPUS
    raw_bytes = p.read_bytes()
    raw = yaml.safe_load(raw_bytes)
    pages = {}
    for d in raw["pages"]:
        if d["url"] in pages:
            raise ValueError(f"duplicate url {d['url']}")
        pages[d["url"]] = Page(
            url=d["url"],
            title=d["title"],
            published=str(d["published"]),
            snippet=d["snippet"],
            text=d.get("text", ""),
            authority=d.get("authority", "low"),
            status=int(d.get("status", 200)),
            tags=tuple(d.get("tags", [])),
        )
    return FixtureWeb(
        version=raw["version"],
        pages=pages,
        contexts=raw.get("contexts", {}),
        content_hash=hashlib.sha256(raw_bytes).hexdigest()[:16],
    )
