---
name: dashboard-design
description: Visual and interaction standards for the Agent Reliability Studio dashboard (identity, tokens, layout, components). Use when adding or changing any page or component in apps/web.
---
# Dashboard design standards

Source of truth: `docs/DESIGN_SYSTEM.md` and the tokens in `apps/web/app/globals.css`. Read both before changing UI.

## Identity in one paragraph
A measurement instrument, not a SaaS template. Cool graphite neutrals, ONE accent (cobalt) meaning "the thing being measured", IBM Plex Sans/Mono, 2-4px radii, no shadows, no gradients, no glass. The mark is a confidence interval (two caps, a bar, a point). Never add robots, orbs, sparkles.

## Rules that keep it from looking generated
- Not everything is a card. Group with type, alignment and one hairline rule. Never nest cards. A page has at most one boxed region; the rest is open layout.
- Metrics live in a **Ledger** (`components/ledger.tsx`): metric | baseline | candidate | change | basis. Do not build grids of identical KPI tiles.
- Labels are sentence case. No ALL-CAPS eyebrows, no `—` spaced taglines, no icons beside headings. Badges are flat tinted text (`Badge`), used only for verdicts, evidence kind, and gate state.
- Numbers: `.mono .num`, tabular, right-aligned in tables, always with n or a CI nearby (`Basis` column).
- Colour: ok/warn/bad are verdict colours only. `info` (slate) means synthetic/illustrative. Accent = live/selected/link. Colour is never the only signal (word + colour).
- Evidence kind is first-class: `KindBadge` on every run/comparison; live and synthetic numbers are never summed, charted together, or in one table without a kind column.
- Headline of a page is the question it answers (Overview: "Did the latest change improve reliability…?"). Verdict text comes from persisted evidence (`comp.explanation`), never from component code. Never write "improvement" if the interval includes zero.

## Layout
Sidebar 212px (groups: Evidence, Evaluators, Release, Reference), content max 1280px. `grid-cols-1` + `min-w-0` on every grid child, tables inside `.scroll-x`, long mono values `[overflow-wrap:anywhere]`. Breakpoints: 1440, 1280, 1024, 768, 390, 360.

## States
Server pages catch fetch errors into `ErrorState` (network / 403 demo / 404 / 429 / 409 / 5xx distinct). `loading.tsx` skeletons, informative `EmptyState`. Every visible control works; no placeholder buttons.

## Verify
`node apps/web/tests/visual-qa.mjs` (see `visual-qa` skill), then extend `tests/e2e/smoke.spec.ts`.
