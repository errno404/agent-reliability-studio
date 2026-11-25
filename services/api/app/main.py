"""FastAPI application: typed REST API, request-id logging, safe errors, restricted CORS."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .logging_setup import setup_logging
from .routers import analysis, core, judges
from .security import request_id_ctx

log = logging.getLogger("ars.api")
REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class BodyLimit:
    """Pure-ASGI request body cap. The body is BUFFERED up to the limit before the app sees anything, so a request rejected with
    413 (declared Content-Length OR streamed/chunked bytes) never reaches a handler. Bodies here are tiny (<= 64 KB)."""

    def __init__(self, app, max_bytes: int):  # type: ignore[no-untyped-def]
        self.app, self.max = app, max_bytes

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)

        async def reject() -> None:
            body = b'{"detail":"request body too large"}'
            headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
            ]
            await send({"type": "http.response.start", "status": 413, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max:
            return await reject()
        chunks: list[bytes] = []
        total = 0
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return None
            total += len(msg.get("body", b""))
            if total > self.max:
                return await reject()
            chunks.append(msg.get("body", b""))
            if not msg.get("more_body", False):
                break
        replay = iter([{"type": "http.request", "body": b"".join(chunks), "more_body": False}])

        async def replayed():  # type: ignore[no-untyped-def]
            return next(replay, {"type": "http.disconnect"})

        await self.app(scope, replayed, send)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    setup_logging(s.log_level)
    log.info("api starting", extra={"status": "demo" if s.demo_mode else "admin"})
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Agent Reliability Studio API",
        version="0.1.0",
        lifespan=lifespan,
        description="Evaluation infrastructure for measuring, debugging, comparing and improving tool-using AI agents. "
        "Demo data is synthetic fixture evidence.",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.add_middleware(BodyLimit, max_bytes=s.max_body_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        supplied = request.headers.get("x-request-id", "")
        rid = supplied if REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex[:12]  # never echo unbounded/odd input
        token = request_id_ctx.set(rid)
        t0 = time.perf_counter()
        try:
            resp = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        resp.headers["x-request-id"] = rid
        resp.headers["x-content-type-options"] = "nosniff"
        # Only successful, anonymous GETs of public read-only data are cacheable; errors and admin-authenticated traffic never are.
        public = (
            request.method == "GET"
            and resp.status_code == 200
            and "x-admin-token" not in request.headers
            and request.url.path.startswith(
                ("/api", "/overview", "/comparisons", "/gates", "/failures", "/judges", "/policies")
            )
        )
        resp.headers["cache-control"] = "public, max-age=15" if public else "no-store"
        if not request.url.path.startswith(("/health", "/ready")):
            log.info(
                "request",
                extra={
                    "path": request.url.path,
                    "status": resp.status_code,
                    "ms": round((time.perf_counter() - t0) * 1000, 1),
                },
            )
        return resp

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")  # full trace stays in server logs only
        detail = "internal server error" if s.environment == "production" else f"{type(exc).__name__}: {exc}"
        return JSONResponse({"detail": detail, "request_id": request_id_ctx.get()}, status_code=500)

    app.include_router(core.router)
    app.include_router(analysis.router)
    app.include_router(judges.router)
    return app


app = create_app()
