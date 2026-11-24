# Security

The public demo uses **synthetic data only**. The one secret-like string is `DEMO_SECRET_DO_NOT_REVEAL_7F2A`, a harmless red-team canary.

## Threat model in one paragraph
A public, read-only dashboard + API backed by seeded synthetic data; optional local/admin mode that can execute evaluations (including local scripts for
the coding agent). Attackers: anonymous internet users (abuse public endpoints, spoof headers, inject content), malicious dataset/trace content, and
accidental leakage of secrets into traces.

## Controls

| Area | Control |
|---|---|
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
Annotator identities are self-declared handles (no authentication) — treat annotation data as untrusted crowd input. Rate limiting is per-process; use an
edge limiter for multi-instance deployments. The coding agent runs scripts on the host: do not enable it on a shared server without a real sandbox (container/VM).

## Reporting
Open a private security advisory on the repository.
