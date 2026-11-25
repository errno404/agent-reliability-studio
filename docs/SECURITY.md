# Security

The public demo uses **synthetic data only**. The one secret-like string is `DEMO_SECRET_DO_NOT_REVEAL_7F2A`, a harmless red-team canary.

## Threat model in one paragraph
A public, read-only dashboard + API backed by seeded synthetic data; optional local/admin mode that can execute evaluations (including local scripts for
the coding agent). Attackers: anonymous internet users (abuse public endpoints, spoof headers, inject content), malicious dataset/trace content, and
accidental leakage of secrets into traces.

## Trust boundaries (read this first)
| Surface | Public demo | Local / operator |
|---|---|---|
| Browse seeded synthetic data and the published real experiment | yes | yes |
| Anonymous annotation | yes, stored as `public_untrusted`, never evidence | yes |
| Authenticated (trusted) human annotation / adjudication | **disabled** (403) | `POST /api/annotation/trusted[/adjudicate]` with `X-Admin-Token` |
| Execute evaluations (synthetic) | no | admin token |
| **Live LLM execution** (spends the operator's own CLI quota) | **no** | admin token **and** a server-side allowlist/clamp on model, budget and timeout; the CLI is operator-only |
| Coding-agent execution | no | admin token **and** `ENABLE_CODING_EXECUTION=true`; **not a sandbox** (see below) |
| Calibrate a judge over HTTP | no | admin token, capped items and wall-clock deadline (504, nothing recorded) |

## Controls

| Area | Control (and the test that proves it) |
|---|---|
| Persisted content | Everything free-form stored for a sample - input, output, tool args/results, **span names/attributes**, assertion evidence, judge rationale, error text - is redacted **before** it is written; exported artifacts (distilled candidates, experiment bundles) are redacted too. Structure and numerics survive. `test_redaction_canary.py` plants 7 canary secrets in every agent-influenced field, runs the real pipeline, and scans **every column of every table, every read endpoint and the distill output**. (Writing it found a real leak: span attributes were stored unredacted.) Stored strings are capped at 20,000 chars and 500 spans/sample. |
| Secrets | None committed; `.env*` git-ignored except `.env.example`; no chain-of-thought is requested or stored (thinking blocks from the live harness are never read). |
| Public demo mode | `DEMO_MODE=true` (default): every mutating endpoint returns 403. Non-demo mutation needs `X-Admin-Token` (constant-time compare). **Failed attempts are rate-limited** (10/min/client); while the window is full even the right token is refused, so there is no oracle. |
| Public writes | Anonymous annotation is rate-limited, capped, validated, append-only and **stored as `public_untrusted`**. Anonymous adjudication is never flagged adjudicated. Untrusted handles never count toward a consensus claim and never change a reference label or gate. |
| API hardening | Request ids are validated (`[A-Za-z0-9._-]{1,64}`, else replaced); request bodies are capped at 64 KB by a pure-ASGI limiter (Content-Length **and** streamed/chunked bytes -> 413); only successful anonymous GETs are publicly cacheable (errors, POSTs and admin traffic are `no-store`); all list endpoints take a bounded `limit`; no response contains an absolute filesystem path (`test_api_hardening.py`). |
| Errors | **`ENVIRONMENT` defaults to `production`**: clients get `internal server error` + request id; details stay in logs. Dev scripts opt in with `ENVIRONMENT=development`. |
| Regex | Patterns come only from trusted, versioned datasets (no API accepts one). Defence in depth: length cap, **nested unbounded repetition and back-references rejected** (the assertion becomes INVALID, never a hang or a silent pass), and the scanned subject is capped at 100k chars. Not a timeout: a pathological-but-accepted pattern is still possible, hence "trusted datasets only". |
| Coding-agent execution | **A temp directory is not a sandbox, and this is not one either.** What exists: dataset commands must match `PYTHON -m pytest|unittest <relative args>` (no `-c`, absolute/parent paths or metacharacters); plan write/read paths are resolved inside the workspace; fixture repos may contain no symlinks; the environment is scrubbed; CPU-time and written-file-size rlimits; output captured to size-limited files and truncated; process-group kill on timeout. What does **not** exist: filesystem confinement outside the workspace, network isolation, memory caps on macOS. Therefore it is repo-authored scripted plans only, admin-gated, off by default, and must never be exposed publicly; a real sandbox (container/VM with no network) is required before running untrusted agent code. |
| Live LLM harness | The CLI runs with only the three fixture MCP tools (`--strict-mcp-config --tools ""`), no user settings/hooks/plugins, a scrubbed environment, per-run budget and timeout, process-group kill, stdin task text (a task beginning with `-` cannot become a flag). It reads no credentials: it uses the operator's own login. Live specs are clamped server-side (model allowlist, budget <= $2, timeout <= 300 s). |
| Worker | Leases with fencing tokens, independent heartbeat, atomic stale recovery, bounded attempts (`test_worker_leases.py`, SQLite and PostgreSQL). Single-database lease: **no distributed-consensus claim**. |
| Command execution | No shell anywhere. Subprocesses use argv lists, timeouts and process-group kill. |
| Client identity | The web proxy drops client-supplied forwarding headers; `TRUSTED_PROXY_HOPS` defaults to 0 everywhere (including the Render blueprint) because Render's `X-Forwarded-For` behaviour is **not verified** from its docs. uvicorn trusts forwarded IPs only from `FORWARDED_ALLOW_IPS`. |
| CORS | Allow-list from `CORS_ORIGINS`; methods GET/POST. |
| Containers / deploy | Non-root users, slim images, health checks, compose binds API and web to loopback, `.dockerignore` excludes env files. Compose DB credentials are local-only defaults (DB is not published). `arizephoenix/phoenix:latest` is optional and unpinned (flagged). Render blueprint: free-tier compatible (private services have no free tier), free Postgres expires after 30 days. **Nothing is deployed by this repository's tooling.** |
| Supply chain | `check_pins.py` reads pins from the **trusted git baseline** and fails closed (no removal/rewrite/un-freeze; new versions need matching hash + evidence; shared-dependency changes need new re-measurement evidence). Datasets are hash-frozen. |

## Known limitations
- Coding execution and the legacy `ClaudeCodeAdapter` are **not sandboxed** (above). Do not expose them.
- Anonymous annotation is per-process rate limited and shares one bucket behind a proxy with `TRUSTED_PROXY_HOPS=0`; the 5,000-row cap is global. Treat all of it as untrusted crowd input.
- Rate limiters are in-process (single API instance). Use an edge limiter when scaling out.
- Lease fencing leaves a small check-then-write window; the unique `(run, case, sample)` constraint and token-conditional completion bound the damage.
- The live harness depends on a third-party CLI whose behaviour can change; the resolved model and harness config are recorded per run, and alias drift fails validation.
- CI trust model: see `docs/CI.md` (evaluator code is taken from the trusted base, never from the PR).

## Reporting
Open a private security advisory on the repository.

_Reviewed by independent read-only reviewers during the build; fixes are covered by tests (see `services/api/tests/test_api.py`, `packages/evalcore/tests/test_core.py`)._
