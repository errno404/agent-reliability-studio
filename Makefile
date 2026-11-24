# Agent Reliability Studio — developer commands. `make demo` gives a populated local app with NO API keys.
SHELL := /bin/bash
NODE22 := $(HOME)/.nvm/versions/node/v22.23.4/bin
export PATH := $(if $(wildcard $(NODE22)),$(NODE22):,)$(PATH)
PYENV := source scripts/env.sh &&

.PHONY: help setup dev demo seed test test-py test-web e2e lint typecheck build verify screenshots pins gen-types docker clean

help:            ## list commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/' | column -t -s '—'

setup:           ## install Python + web dependencies (Node >= 22 required for the web app)
	uv sync --python 3.13
	@chflags -R nohidden .venv 2>/dev/null || true
	cd apps/web && npm install
	$(PYENV) uv run ars db upgrade

seed:            ## load the synthetic demo data (idempotent)
	$(PYENV) uv run ars demo seed

dev:             ## API (:8000) + web (:3000) with hot reload
	bash scripts/dev.sh

demo: setup seed ## populated app, zero API keys: opens on http://localhost:3000
	$(PYENV) uv run ars demo verify
	bash scripts/dev.sh

test-py:         ## Python tests (+ evalcore coverage gate >= 85%)
	$(PYENV) uv run pytest --cov=evalcore --cov-fail-under=85 -q -p no:cacheprovider

test-web:        ## frontend unit tests
	cd apps/web && npx vitest run

test: test-py test-web ## all unit/integration tests

e2e:             ## Playwright smoke tests (starts a seeded API + the production web build)
	cd apps/web && npm run build && npx playwright test

lint:            ## ruff + eslint
	$(PYENV) uv run ruff format --check . && uv run ruff check .
	cd apps/web && npx eslint .

typecheck:       ## pyright + tsc
	$(PYENV) uv run pyright
	cd apps/web && node --max-old-space-size=3072 node_modules/typescript/bin/tsc --noEmit

build:           ## production web build
	cd apps/web && npm run build

pins:            ## enforce frozen agent versions
	$(PYENV) uv run python scripts/check_pins.py

gen-types:       ## regenerate the typed frontend API layer from the FastAPI OpenAPI spec
	$(PYENV) uv run ars openapi --out apps/web/lib/openapi.json
	cd apps/web && npx openapi-typescript lib/openapi.json -o lib/api-types.ts

verify: lint typecheck test pins build e2e ## everything CI runs
	$(PYENV) uv run python scripts/verify_demo.py

screenshots:     ## capture the README screenshots from a seeded local stack
	$(PYENV) uv run python scripts/capture_screenshots.py

docker:          ## full stack in containers (Postgres + API + web)
	docker compose up --build

clean:
	rm -rf .pytest_cache .ruff_cache apps/web/.next apps/web/test-results ars.db ars.db-wal ars.db-shm
