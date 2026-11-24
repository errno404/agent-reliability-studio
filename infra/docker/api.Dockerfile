# syntax=docker/dockerfile:1.7
# API + worker image (same code, different command). Build context = repo root.
FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/
WORKDIR /app

FROM base AS build
# deps first (cached), then sources
COPY pyproject.toml uv.lock ./
COPY packages/evalcore/pyproject.toml packages/evalcore/pyproject.toml
COPY packages/demo_agents/pyproject.toml packages/demo_agents/pyproject.toml
COPY mcp/fixture_web/pyproject.toml mcp/fixture_web/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
RUN mkdir -p packages/evalcore/src/evalcore packages/demo_agents/demo_agents mcp/fixture_web/fixture_web services/api/app \
 && touch packages/evalcore/src/evalcore/__init__.py packages/demo_agents/demo_agents/__init__.py \
          mcp/fixture_web/fixture_web/__init__.py services/api/app/__init__.py \
 && uv sync --frozen --no-dev --no-install-workspace --all-packages
COPY packages packages
COPY mcp mcp
COPY services services
COPY datasets datasets
COPY fixtures fixtures
RUN uv sync --frozen --no-dev --all-packages

FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 ars
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" DEMO_MODE=true ENVIRONMENT=production PORT=8000
USER ars
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1
# Migrate, seed the synthetic demo (idempotent), then serve.
CMD ["sh", "-c", "ars db upgrade && ars demo seed && exec ars serve --host 0.0.0.0 --port ${PORT}"]
