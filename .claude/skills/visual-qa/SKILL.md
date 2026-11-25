---
name: visual-qa
description: Browser-based visual inspection and responsive testing for the dashboard. Use after any UI change, before declaring it done.
---
# Visual QA

Tooling: `apps/web/tests/visual-qa.mjs` renders every main page at 1440/1280/1024/768/390/360 in light and dark, fails on horizontal overflow, and reports console errors.

```bash
export PATH=$HOME/.nvm/versions/node/v22.23.4/bin:$PATH
make dev    # API :8000 + web :3000, seeded (ars demo seed)
node apps/web/tests/visual-qa.mjs /tmp/vqa      # env: SIZES=1440,390 THEMES=dark PAGES=overview,compare
```
Then LOOK at the PNGs (Read tool). Passing tsc or lint is not evidence it looks right.

Checklist per page: first screen answers the page's question; hierarchy (one h1, one primary region); alignment of numeric columns; no card-in-card; no empty tall panels; long hashes/tool names wrap or scroll inside their container; kind badge present; both themes legible (contrast); 390px layout is adapted (scrolling tables, stacked comparison), not just shrunk; nothing clipped under the sticky bar.
Find the cause of overflow with a script that lists elements whose `right` exceeds the viewport and have no overflow-x ancestor. Typical causes: a grid child without `min-w-0`, a global `white-space: nowrap`, long mono strings.
Interactive states to exercise: nav drawer, theme toggle, filters, span selection in a trace, `<details>` expanders, keyboard Tab order.
Do one focused correction pass; do not loop on taste.
