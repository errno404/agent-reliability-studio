---
name: dashboard-design
description: Visual and interaction standards for the Next.js dashboard. Use when adding or changing any page or component in apps/web.
---
# Dashboard design standards
- Aesthetic: serious observability tool — dense, crisp, evidence-first. Tokens live in `app/globals.css` (light/dark). One accent; ok/warn/bad/info colours are semantic only. No decorative gradients.
- Every rate shows **n** and a CI (or a tooltip). Decisions use `DecisionBadge`; calibration state is never hidden (`CALIBRATED — allowed for gating` vs `NOT CALIBRATED — diagnostic only`).
- Server pages catch fetch errors into `ErrorState` (network / 403 demo / 404 / 429 / 409 / 5xx are distinct). Provide skeletons (`loading.tsx`), empty states and disabled states.
- Responsive: 1440 desktop, laptop, tablet, 390 mobile. Cards need `min-w-0`; tables scroll inside `.scroll-x` and offer a card list on mobile; the trace waterfall falls back to a list.
- Accessibility: visible `:focus-visible`, `aria-sort`, labelled landmarks, charts backed by an `sr-only` table, `prefers-reduced-motion`. Colour is never the only signal.
- Data comes only from the typed client in `lib/api.ts` (types generated from OpenAPI via `make gen-types`). The browser calls same-origin `/api/*` (runtime proxy); never hard-code the API URL.
- Verify by opening the page (desktop + 390px) and extending `tests/e2e/smoke.spec.ts`.
