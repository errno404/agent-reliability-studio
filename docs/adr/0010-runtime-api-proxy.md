# 0010 — Same-origin `/api` proxy resolved at runtime
**Status:** accepted
**Context:** Next.js `rewrites()` bake their destination at build time, which broke containerised/Render deployments where the API URL is only known at runtime.
**Decision:** A route handler forwards `/api/*`, `/docs`, `/openapi.json` to `API_URL` per request; it drops client forwarding headers and re-asserts a client address only with `TRUSTED_PROXY_HOPS`.
**Consequences:** One image runs anywhere; one extra hop; the API need not be reachable from browsers (on Render's free tier it is a public read-only web service; see render.yaml).
