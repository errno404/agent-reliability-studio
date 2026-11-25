---
name: data-visualization
description: Standards for statistical charts in the dashboard (confidence intervals, experiment comparisons, failure distributions, trace waterfalls). Use when adding or changing any chart.
---
# Data visualization standards

1. **Show uncertainty first.** A difference is drawn as a point + 95% interval on a zero line with the non-inferiority margin (`CiPlot`). Never a bare bar for a delta. Rates show a Wilson interval or n.
2. **Zero and margin are always drawn.** Region left of the margin is tinted `--bad-soft`. If the interval includes zero, the caption must say it is not a demonstrated improvement.
3. **Honest axes.** Rates 0-100%; deltas symmetric around zero where possible. No truncated bars. No dual axes.
4. **Chart only what the evidence supports.** Do not chart live and synthetic runs together. A chart needs a stated question; delete charts that only fill space.
5. **Encoding.** Baseline = neutral grey, candidate = accent, regression = `--bad`, improvement = `--ok`. Max 2 hues per chart plus semantic colour. Direct labels over legends when possible.
6. **Accessible by construction.** Every figure has `aria-label`/`<title>` with the numbers, plus an sr-only table or the Ledger beside it. No colour-only meaning.
7. **No animation** on data marks (`isAnimationActive={false}`): screenshots and reduced-motion users get the final state immediately.
8. **Traces.** Spans render as an indented waterfall on a shared time axis; selection opens a detail inspector; arguments/results are structured key-value mono rows, never raw JSON dumps; reasoning content is never shown.
9. **Data comes from the API**, typed in `lib/api.ts`; no hardcoded numbers in components.
