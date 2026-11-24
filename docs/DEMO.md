# Demo walkthrough

Start: `make demo` → <http://localhost:3000> (or `docker compose up --build`). **Everything is synthetic fixture evidence.**

## Nine steps (≈ 5 minutes)

1. **Overview** — read the headline: `support:v1 → support:v2`, `IMPROVEMENT`, `CI gate: PASS`. Note every rate shows `n` and a 95% CI.
2. **Candidate vs baseline** — KPI tiles show outcome / trajectory / component / policy separately, plus `pass^k` (87% vs 30%) and `pass@k`.
3. **Compare → "Support v1 → v2"** — the CI plot sits entirely above zero; the −5 pt non-inferiority margin is drawn; 30 matched cases; validity panel is empty.
4. **What changed?** — "Localized regression: 'address' cases fell 11 points", plus new failure modes `wrong_tool_arguments`, `state_mutation_failure`.
5. **Open a regressed case** — `sup-17-address-unit-apt`: expected assertions, then the diff.
6. **Trajectory diff** — same tools, but `update_shipping_address` arguments changed: baseline `city: "Sollund"`, candidate `city: "Apt 5"`. Open the trace to see the OTel spans.
7. **Judges** — the strict judge is `CALIBRATED — allowed for gating` (κ 0.97, FPR 0%); the lenient one is `NOT CALIBRATED — diagnostic only` (κ 0.47, FPR 50%). Open *Annotate items* to label blind.
8. **CI / Release Gates** — pass; **inconclusive** (30 < 50 cases under `production`); **invalid** (draft dataset, different hash); and a gate **blocked because the judge is not calibrated**.
9. **Methodology** — the glossary explains pass@k, pass^k, κ, margin and the gate in plain language.

## Two-minute script

> "Agents fail in ways accuracy can't see. This is infrastructure that measures that. *(Overview)* v2 beat v1 by 50 points and the gate passed — with a confidence
> interval, a margin and a sample size on screen. *(Compare)* But the 'what changed' panel found a localized regression: address changes fell. *(Case diff)* Here is the
> exact bug: v2 put the apartment number in the `city` argument. *(Judges)* LLM judges are models too, so each one is calibrated: this one is admitted; this one isn't,
> and CI refuses to gate on it. *(Gates)* The same gate says *inconclusive* when evidence is thin and *invalid* when two runs aren't comparable. All of it runs with zero API keys."

## Reproduce the story from the CLI

```bash
ars eval run --agent support:v1 --dataset support:v1 --samples 3 --seed 7 --run-id a
ars eval run --agent support:v2 --dataset support:v1 --samples 3 --seed 7 --run-id b
ars eval compare --baseline a --candidate b --policy demo-20      # exit 0
ars eval diff a b                                                # trajectory changes per case
```
