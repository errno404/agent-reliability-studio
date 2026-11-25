# Design system

Agent Reliability Studio is a measurement instrument, so the interface is built like one: quiet surfaces, exact numbers, and colour reserved for verdicts. This file is the reference for anyone changing the UI. The enforceable parts live in `apps/web/app/globals.css` (tokens), `apps/web/components/` (primitives) and the project skills in `.claude/skills/`.

## Identity

- **Mark.** A confidence interval: two whisker caps, the bar between them, and the point estimate (`components/mark.tsx`, `app/icon.svg`). It says what the product does: report an estimate *with* its uncertainty.
- **Name treatment.** "Agent Reliability Studio", set in IBM Plex Sans semibold, two lines in the sidebar. No tagline.
- **Voice.** Plain, specific, sentence case. Verdicts are stated as what the evidence supports ("No meaningful regression. The interval includes zero, so this is not a demonstrated improvement.").

## Principles

1. **The question comes first.** Each page opens with the question it answers; the Overview asks "Did the latest change improve reliability, cause a regression, or leave us without enough evidence?" and answers it from the latest valid real-model comparison.
2. **Uncertainty is part of the number.** Differences are drawn as an interval against zero and the non-inferiority margin. Rates carry n or a CI in the *Basis* column.
3. **Evidence kind is never ambiguous.** Live-model results and synthetic scripted results are labelled everywhere, never summed, and never in one chart.
4. **Structure instead of boxes.** One boxed region at most per view. Hierarchy comes from type size, weight, alignment and a single hairline rule. No cards inside cards.
5. **Colour carries meaning only.** Accent = the live/selected thing. ok/warn/bad = verdicts. Slate = synthetic/illustrative. Everything else is neutral.

## Typography

| Role | Face | Notes |
|---|---|---|
| UI and prose | IBM Plex Sans 400/500/600 | 14px base, `letter-spacing: -0.003em` |
| Numbers, hashes, tool names, code | IBM Plex Mono 400/500 | `.mono`, tabular figures, slashed zero |
| Page question | Plex Sans 600, 22-26px | one per page |
| Section heading | Plex Sans 600, 15px | |
| Table header / caption | Plex Sans 500, 12px, `--muted` | sentence case, never all-caps |

Line length for prose is capped at ~62ch.

## Colour tokens (light / dark)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` / `--panel` / `--panel-2` | #f5f6f8 / #fff / #eff1f4 | #0a0c10 / #101318 / #161a21 | page, surface, subtle fill |
| `--line` / `--line-strong` | #dfe2e8 / #c4c9d2 | #232830 / #363d49 | hairlines, table header rule |
| `--fg` / `--muted` / `--faint` | #0e1319 / #4d5767 / #5f6a7b | #e9edf3 / #a0aab9 / #7b8696 | text; faint is captions only |
| `--accent` | #1f4fd8 | #7ea3ff | live model, links, selection, intervals |
| `--ok` `--warn` `--bad` (+ `-soft`) | #0e7a47 #8a5a00 #b3261e | #4fd39a #f0b84f #ff8277 | verdicts only |
| `--info` (+ soft) | #475569 | #a3afc2 | synthetic / illustrative |

All text pairs meet 4.5:1 in both themes (verified numerically; the lowest are `--faint` on `--panel-2` in light at 4.6:1 and `--ok` on `--ok-soft` at 4.67:1).

## Shape and depth

Radius 2px (badges), 3px (controls), 4px (panels). No shadows, no gradients, no blur. A 1px border or a subtle fill separates regions, never both.

## Components

| Component | Purpose |
|---|---|
| `Ledger` | Baseline → candidate → change → basis table. Replaces KPI tile grids. |
| `CiPlot` | Delta with 95% interval, zero line and non-inferiority margin; carries a text alternative. |
| `Badge` / `DecisionBadge` / `KindBadge` | Flat tinted text for verdict, decision, evidence kind. Sentence case. |
| `Stat` | A single metric with n / CI, used only inside detail views. |
| `Card` / `CardHeader` | The one boxed region on detail pages. |
| `HashChip` | Mono, copyable identity values (dataset, fixture, agent, evaluator hashes). |
| Trace waterfall + inspector | Indented spans on a shared time axis; selected span opens structured attributes. No reasoning content, no raw JSON dumps. |
| `Shell` | Grouped sidebar (Evidence, Evaluators, Release, Reference), kind legend, theme toggle, mobile drawer. |

## Chart conventions

See `.claude/skills/data-visualization/SKILL.md`: interval first, zero/margin always drawn, honest axes, baseline grey vs candidate accent, no animation, every figure has a text equivalent.

## Responsive behaviour

Designed at 1440, 1280, 1024, 768, 390 and 360px. Below 1024 the sidebar becomes a drawer; two-column comparison regions stack; tables scroll horizontally inside their own container; long mono values wrap. `apps/web/tests/visual-qa.mjs` fails on any page-level horizontal overflow at those sizes in both themes.

## Accessibility

Skip link, labelled landmarks, visible focus ring, `aria-current` on navigation, `th scope`, sr-only/aria text for charts, reduced-motion support, no colour-only meaning. Checklist: `.claude/skills/accessibility-review/SKILL.md`.

## What we deliberately avoid

Gradients and glass, glowing "AI" imagery, KPI tile grids, ALL-CAPS eyebrows, pill-shaped decorative badges, an icon beside every heading, entrance animations, and charts that exist only to fill space.
