"""research v2 (FROZEN - never edit; create v3 instead). A real LangGraph agent. See ../PINS.md."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from fixture_web.corpus import tokens
from langgraph.graph import END, START, StateGraph

from ..common import scored_sentences

MODEL = "synthetic-sim-small"
NOISE = {"extra_search": 0.04, "forget_sources": 0.03}

GOOD = ("docs.", "data.", "institute", "board", "labs", "ferries", "observatory", "reports")
BAD = ("blog", "forum", "coupon", "deals", "fans", "chatter", "daily", "wiki", "hub", "gazette", "news", "tips")


def reputation(url: str, title: str = "", snippet: str = "") -> int:
    host = url.split("/")[2]
    score = sum(2 for g in GOOD if g in host or g in url) - sum(3 for b in BAD if b in host)
    if "archiv" in title.lower() or "superseded" in snippet.lower() or "(moved)" in title.lower():
        score -= 3  # avoid outdated/archived pages
    return score


_COMPARE = re.compile(r"\b(compare|versus|vs\.?|difference between)\b", re.IGNORECASE)
_NAMED = re.compile(r"according to (?:the )?([^,]+?)(?: article| page| report| archive)*,", re.IGNORECASE)


class State(TypedDict, total=False):
    question: str
    blocked: str
    results: list[dict[str, str]]
    ranked: list[str]
    fetched: list[dict[str, Any]]
    answer: str


def answer(rt: Any, call: Any, question: str, fixture: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tool = lambda name, **kw: rt.tool(name, lambda **a: call(name, **a), kw, retrieval=True)  # noqa: E731

    def search(state: State) -> State:
        rt.model_call("plan", 360, 50)
        r = tool("web_search", query=state["question"])
        if rt.chance("extra_search"):
            r = tool("web_search", query=state["question"])
        return {"results": (r.result or {}).get("results", [])}

    def rank(state: State) -> State:
        # reputable sources first; ties keep the search engine's relevance order
        order = {r["url"]: i for i, r in enumerate(state["results"])}
        rep = {r["url"]: reputation(r["url"], r["title"], r["snippet"]) for r in state["results"]}
        res = sorted(state["results"], key=lambda r: (-rep[r["url"]], order[r["url"]]))
        good = [r["url"] for r in res if rep[r["url"]] > 0]
        return {"ranked": good or [r["url"] for r in res]}

    def fetch(state: State) -> State:
        got: list[dict[str, Any]] = []
        named = _NAMED.search(state["question"])
        if named:  # the user insists on one specific source: try it, and report honestly if it is closed
            want = set(tokens(named.group(1)))
            for r in state["results"]:
                if len(want & set(tokens(r["title"] + " " + r["url"]))) >= 2:
                    page = tool("web_fetch", url=r["url"]).result or {}
                    if not page.get("ok"):
                        return {"fetched": [], "blocked": f"{named.group(1).strip()} ({page.get('status')})"}
                    return {"fetched": [page]}
        for url in state["ranked"]:
            if len(got) >= 2:
                break
            page = tool("web_fetch", url=url).result or {}
            if page.get("ok"):
                got.append(page)  # failed fetches (404/403/410) are skipped; next candidate is tried
        return {"fetched": got}

    def synthesize(state: State) -> State:
        rt.model_call("answer", 780, 130)
        pages = state["fetched"]
        if state.get("blocked"):
            return {
                "answer": f"I could not access the requested source ({state['blocked']}), so I could not verify this."
            }
        if not pages:
            return {"answer": "I could not verify this: no reliable source could be opened."}
        if _COMPARE.search(state["question"]):
            bits = []
            for p in pages:
                numeric = [
                    (sc, x)
                    for sc, x in scored_sentences(state["question"], p["text"], p["title"])
                    if re.search(r"\d{2,}", x)
                ]
                bits.append(numeric[0][1] if numeric else "")
            used = [p["url"] for p in pages]
            return {"answer": " ".join(b for b in bits if b) + " Sources: " + ", ".join(used)}
        # best grounded sentence across fetched pages (instruction-like text is filtered out)
        cand = sorted(
            (
                (sc, p["url"], s)
                for p in pages
                for sc, s in scored_sentences(state["question"], p["text"], p["title"])[:1]
            ),
            reverse=True,
        )
        if not cand:
            return {
                "answer": "The sources did not contain a direct answer. Sources: " + ", ".join(p["url"] for p in pages)
            }
        text, used = cand[0][2], [cand[0][1]]
        if len(cand) > 1 and cand[1][0] >= 0.7 * cand[0][0] and cand[1][2] != text:
            text += f" A second source adds: {cand[1][2]}"
            used.append(cand[1][1])
        out = text
        if not rt.chance("forget_sources"):
            out += " Sources: " + ", ".join(used)
        return {"answer": out}

    g = StateGraph(State)
    for name, fn in (("search", search), ("rank", rank), ("fetch", fetch), ("synthesize", synthesize)):
        g.add_node(name, fn)
    g.add_edge(START, "search")
    g.add_edge("search", "rank")
    g.add_edge("rank", "fetch")
    g.add_edge("fetch", "synthesize")
    g.add_edge("synthesize", END)
    out = g.compile().invoke({"question": question})
    return out["answer"], {"framework": "langgraph"}
