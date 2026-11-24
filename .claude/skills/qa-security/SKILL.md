---
name: qa-security
description: QA and security checklist for this repo. Use before merging changes, when adding endpoints/adapters, or when touching redaction, subprocess execution, deployment config or CI.
---
# QA & security checklist
- **Run:** `make verify` (ruff, pyright, pytest+coverage, vitest, eslint, tsc, pins, build, Playwright, demo verify).
- **Secrets:** none committed; only the synthetic `DEMO_SECRET_…`. `.env*` ignored. Redaction (keys, patterns, known secrets, truncation) happens *before* storage/export.
- **Execution:** no shell from the web; subprocesses use argv lists, timeouts and process-group kill; workspaces are temp dirs; file assertions reject absolute/`..` paths; coding execution is off unless `ENABLE_CODING_EXECUTION=true` locally.
- **Public surface:** `DEMO_MODE` blocks mutations; CORS restricted; rate limits on public writes; production errors hide stack traces; forwarded client IPs are trusted only via `TRUSTED_PROXY_HOPS` / `FORWARDED_ALLOW_IPS` (never `*` on a public API).
- **Config consistency:** if a comment says a service is private, the compose/Render config must make it so (loopback port bind, `pserv`).
- **Review prompts:** treat automated security-review findings as input — fix or document why they don't apply; add a regression test for each fix.
