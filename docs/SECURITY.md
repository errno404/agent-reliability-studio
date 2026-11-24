# Security

The public demo uses **synthetic data only**. The one secret-like string is `DEMO_SECRET_DO_NOT_REVEAL_7F2A`, a harmless red-team canary.

## Threat model in one paragraph
A public, read-only dashboard + API backed by seeded synthetic data; optional local/admin mode that can execute evaluations (including local scripts for
the coding agent). Attackers: anonymous internet users (abuse public endpoints, spoof headers, inject content), malicious dataset/trace content, and
accidental leakage of secrets into traces.

## Controls

| Area | Control |
|---|---|
| Persisted content | Everything free-form stored for a sample (input, output, tool args/results, assertion evidence, error text) is redacted **before** it is written, not just span attributes. Key matching is normalised (`x-api-key`, `passwordHash`), patterns cover API keys, JWTs, Slack/Stripe/Google keys, credentialed URLs and Basic auth; usage counters like `input_tokens` are exempt. A test scans the database for the demo canary. |
| Secrets | None committed; `.env*` git-ignored except `.env.example`; redaction (key names, regex patterns for API keys/tokens/PEM, known-secret replacement, truncation) runs **before** traces are stored or exported (`evalcore/redaction.py`, applied in `tracing.py`); no chain-of-thought is requested or stored. Run a secret scanner (e.g. gitleaks) in your own CI. |
| Public demo mode | `DEMO_MODE=true` (default): every mutating endpoint returns 403 via `require_admin`; non-demo mutation needs `X-Admin-Token` (constant-time compare). Coding-agent execution is additionally off unless `ENABLE_CODING_EXECUTION=true`. |
| Public writes | Only annotation/adjudication are open: rate-limited (30/min/client key), capped (5,000 human rows), strict id validation (`fullmatch` + schema pattern, so a trailing newline can't slip through), **append-only** (an existing label is never overwritten, so annotator ids can't be hijacked), stored separately and never used for gating. |
| Command execution | No shell from the web. Subprocesses use argv lists (never `shell=True`), timeouts, **process-group kill** on timeout, temp sandbox directories, and snapshot-based change accounting. Coding runs are local/admin only. |
| Path safety | File assertions reject absolute paths and `..`; the web proxy rejects `..` segments and forwards only under `/api`. |
| Client identity | The web proxy **drops all client-supplied forwarding headers** (`X-Forwarded-*`, `Forwarded`, `X-Real-IP`, …). It re-asserts one address only when `TRUSTED_PROXY_HOPS ≥ 1` (the Nth-from-last `X-Forwarded-For` entry, added by your edge). uvicorn trusts forwarded IPs only from `FORWARDED_ALLOW_IPS` (default loopback; never `*` on a public API). Compose binds the API to loopback; Render runs it as a **private service**. |
| CORS | Allow-list from `CORS_ORIGINS`; methods limited to GET/POST. Browsers talk to the same-origin `/api` proxy anyway. |
| Errors | In `ENVIRONMENT=production` the API returns `internal server error` + a request id; stack traces stay in logs. |
| Logging | Structured JSON with request/run/job/case ids; prompt content is not logged. |
| Containers | Non-root users, slim base images, health checks, `.dockerignore` excludes env files. |
| Dependencies | Versions pinned by `uv.lock` / `package-lock.json`; Node/uv reviewed at pin time; run `pip-audit` / `npm audit` in CI. |
| Supply chain | `check_pins.py` blocks silent changes to published agent versions; datasets are hash-frozen. |

## Known limitations
- **The eval-gate workflow trusts the PR checkout** for the evaluator, `check_pins.py` and datasets, so a PR could change the evaluator to pass itself. Mitigate with CODEOWNERS on `packages/evalcore/**`, `scripts/**`, `datasets/**`, `.github/**`, branch protection, and by pinning third-party actions to commit SHAs.
- The web proxy only forwards `POST /api/annotation*` (8 KB cap, 20 s timeout); failed admin-token guesses are not separately rate-limited (use an edge limiter if you ever expose `DEMO_MODE=false` publicly).
- Annotation rate limiting is per client key; with `TRUSTED_PROXY_HOPS=0` every user shares one bucket, and the 5,000-row cap is global. Self-declared ids can be created in bulk, which could skew agreement statistics: treat them as untrusted.
- Dataset-supplied regexes run without a timeout (ReDoS on a malicious dataset). Datasets are trusted input; the Claude Code adapter also trusts `fixture.commands`, so only run trusted datasets locally.
Annotator identities are self-declared handles (no authentication) — treat annotation data as untrusted crowd input. Rate limiting is per-process; use an
edge limiter for multi-instance deployments. The coding agent runs scripts on the host: do not enable it on a shared server without a real sandbox (container/VM).

## Reporting
Open a private security advisory on the repository.

_Reviewed by independent read-only reviewers during the build; fixes are covered by tests (see `services/api/tests/test_api.py`, `packages/evalcore/tests/test_core.py`)._
