"""MCP server exposing the frozen corpus as three read-only tools, plus a sync in-memory client."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import Client
from mcp.server.mcpserver import MCPServer

from .corpus import FixtureWeb, load_corpus


def build_server(web: FixtureWeb | None = None) -> MCPServer:
    web = web or load_corpus()
    mcp = MCPServer(f"fixture-web-{web.version}",
                    instructions="Frozen synthetic web. Read-only. All hosts are .example and fictional.")

    @mcp.tool()
    def web_search(query: str) -> str:
        """Search the frozen corpus. Returns up to 5 results (url, title, snippet, published)."""
        return json.dumps({"results": web.search(query)})

    @mcp.tool()
    def web_fetch(url: str) -> str:
        """Fetch a page by exact URL. Returns text, or an explicit error (404/403/410)."""
        return json.dumps(web.fetch(url))

    @mcp.tool()
    def read_context(name: str) -> str:
        """Read a named background document (e.g. 'citation_style')."""
        return json.dumps(web.read_context(name))

    return mcp


class McpWebClient:
    """Synchronous helper that talks to the fixture server over a real in-memory MCP session."""

    def __init__(self, web: FixtureWeb | None = None):
        self.web = web or load_corpus()
        self._server = build_server(self.web)

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async def go() -> dict[str, Any]:
            async with Client(self._server) as client:
                res = await client.call_tool(tool, arguments)
                text = "".join(getattr(c, "text", "") for c in res.content)
                if getattr(res, "is_error", False):
                    return {"ok": False, "error": text or "tool error"}
                return json.loads(text)

        return asyncio.run(go())


def main() -> None:  # pragma: no cover - stdio entrypoint
    build_server().run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
