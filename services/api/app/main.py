"""FastAPI application: typed REST API, request-id logging, safe errors, restricted CORS."""

from __future__ import annotations

import logging
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
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        t0 = time.perf_counter()
        try:
            resp = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        resp.headers["x-request-id"] = rid
        resp.headers["x-content-type-options"] = "nosniff"
        resp.headers["cache-control"] = "no-store" if request.method != "GET" else "public, max-age=15"
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
