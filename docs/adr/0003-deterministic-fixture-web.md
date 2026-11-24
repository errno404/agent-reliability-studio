# 0003 — A frozen, deterministic fixture web served over MCP
**Status:** accepted
**Context:** Research-agent evaluation on the live web is irreproducible and unsafe.
**Decision:** A versioned synthetic corpus of `.example` pages (authoritative, conflicting, outdated, low-quality, injection, 403/404/410) with deterministic BM25-lite search, exposed read-only through the official MCP SDK (`web_search`, `web_fetch`, `read_context`). Agents call it over a real MCP session.
**Consequences:** Reproducible, safe prompt-injection tests; the corpus hash feeds the dataset/fixture hash. Limit: a small world.
