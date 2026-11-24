# 0006 — Public demo design
**Status:** accepted
**Decision:** `DEMO_MODE=true` is the default: synthetic seeded data, read-only API (mutations 403), no shell, coding execution disabled, clear "Demo data" indicators, every number labelled synthetic. Seeding is code, idempotent, and runs on first start. Live capability is additive when credentials/admin mode are configured.
**Consequences:** A recruiter sees a fully populated product with zero keys; nothing can be harmed.
