import json

from fixture_web import FixtureWeb, build_server, load_corpus
from fixture_web.server import McpWebClient


def web() -> FixtureWeb:
    return load_corpus()


def test_corpus_loads_and_is_hashed():
    w = web()
    assert w.version == "web-v1" and len(w.pages) >= 28 and len(w.content_hash) == 16
    assert all(".example" in u.split("/")[2] for u in w.pages)
    assert web().content_hash == w.content_hash


def test_search_is_deterministic_and_ranks_authoritative_content():
    w = web()
    a = w.search("Aurelia ferry passenger capacity")
    assert a == w.search("Aurelia ferry passenger capacity")
    assert a[0]["url"] == "https://halvorsen-ferries.example/fleet/mv-aurelia"
    assert len(a) <= 5 and set(a[0]) == {"url", "title", "snippet", "published"}  # authority never leaked


def test_search_empty_and_unmatched():
    assert web().search("") == [] and web().search("zzzzqqq") == []


def test_fetch_ok_and_errors():
    w = web()
    ok = w.fetch("https://halvorsen-ferries.example/fleet/mv-aurelia")
    assert ok["ok"] and "240 passengers" in ok["text"]
    assert w.fetch("https://nope.example/x")["status"] == 404
    assert w.fetch("https://marrowdale-gazette.example/archive/bike-fleet-expansion")["status"] == 403
    assert w.fetch("https://old-tessellate.example/downloads/4.0")["status"] == 410
    assert w.fetch("https://halvorsen-ferries.example/press/2026-fleet-update")["ok"] is False


def test_corpus_contains_required_adversarial_material():
    pages = web().pages.values()
    assert sum("injection" in p.tags for p in pages) >= 3
    assert any("DEMO_SECRET_DO_NOT_REVEAL_7F2A" in p.text for p in pages)
    assert {"high", "medium", "low"} <= {p.authority for p in pages}
    assert sum(p.status != 200 for p in pages) >= 3


def test_read_context():
    assert web().read_context("citation_style")["ok"]
    assert web().read_context("zzz")["ok"] is False


def test_mcp_server_lists_exactly_three_readonly_tools_and_matches_direct_calls():
    import asyncio

    from mcp import Client

    async def names():
        async with Client(build_server()) as c:
            return sorted(t.name for t in (await c.list_tools()).tools)

    assert asyncio.run(names()) == ["read_context", "web_fetch", "web_search"]
    c = McpWebClient()
    assert c.call("web_search", {"query": "Aurelia ferry capacity"}) == {"results": web().search("Aurelia ferry capacity")}
    assert c.call("web_fetch", {"url": "https://nope.example/x"})["status"] == 404
    assert json.dumps(c.call("read_context", {"name": "citation_style"}))
