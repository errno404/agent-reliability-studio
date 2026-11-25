<div align="center">

# Agent Reliability Studio

</div>

**Agent Reliability Studio is an evaluation and release-validation platform for tool-using AI agents. It measures outcomes, trajectories, tool correctness, repeated-run reliability and operational performance, with trace-based debugging, evaluator calibration and statistically defensible comparisons.**

*Did this agent change actually improve reliability — or did we introduce a regression?*

![Overview: the latest real-model experiment answers the question first; the synthetic demonstration is separate](docs/images/dashboard-overview.png)

> **Two kinds of evidence, never blended.** The dashboard's demo suites use **scripted agents with seeded faults** — *synthetic fixture
> evidence* that proves the measurement machinery, not any model. Separately, **experiment 001** measures a **real LLM** (Claude Haiku via
> the Claude Code CLI) *in a controlled synthetic environment* and is labelled `live` everywhere. **No public URL is claimed:** the app is not
> deployed (see [Deployment](#deployment)).

## Experiment 001 — a real LLM agent, measured honestly

*Real LLM behaviour evaluated in a controlled synthetic environment.* A research agent (real model making the decisions) over a frozen,
invented 83-page document collection served over MCP; **102 distinct tasks** in 15 categories (conflicting sources, superseded pages, official
corrections, lookalike entities, prompt injection, 403/404 pages, unanswerable and ambiguous questions…), split **by topic** into dev and
held-out; 3 trials per case; no LLM judge; strict paired comparison.

| Held-out (51 cases × 3 trials) | v1 baseline | v2 candidate |
|---|---|---|
| Task success | 146/153 = 95.4% | 151/153 = 98.7% |
| pass^3 / pass@3 | 0.922 / 0.980 | 0.980 / 1.000 |
| Paired delta (case-clustered bootstrap) | **+3.3 pts, 95% CI [−0.7, +8.5]** → verdict **`no_meaningful_regression`** (non-inferiority, **not** a demonstrated improvement) | |

What happened, including the unflattering parts: the first pilot hit 100% (too easy) so I hardened the benchmark *before* any held-out run; **six of the
first seven "failures" were bugs in my own evaluator**, which I fixed and regression-tested; one real behaviour (fetching URLs inferred from sibling URLs)
drove a single prompt change; on held-out its failures dropped from 5 to 0, but the aggregate gain is within noise. One dev comparison was **correctly
refused as INVALID** because the evaluator code hash changed mid-experiment. Full report, limits and reproduction commands:
[`docs/experiments/001-research-agent-reliability.md`](docs/experiments/001-research-agent-reliability.md); sanitized evidence:
[`evidence/experiments/001-research-agent-reliability/`](evidence/experiments/001-research-agent-reliability/) (the dashboard re-imports it and **recomputes** the comparison).
Not a model benchmark; one model, one author, one synthetic world.

## Why agent evaluation is hard

A final answer can look correct while the agent used the wrong tool, invented an argument, broke a policy, looped, or quietly
got *less* reliable after a prompt or model change. One accuracy number hides all of that. Agent Reliability Studio makes those
failures **measurable**: deterministic assertions, trajectory analysis, calibrated LLM judges, repeated trials, OpenTelemetry
traces, human annotation, and a statistically defensible regression gate that is allowed to answer *"inconclusive"* or
*"invalid comparison"* instead of pretending.

## 30-second demo

```bash
make demo            # installs, migrates, seeds the demo + the published live experiment, runs invariants, starts API + web
# open http://localhost:3000
```

0. **Overview** — leads with the latest **real-model** experiment (research agent v1 → v2): *No regression detected. Improvement not established.* The +3.3 pt difference has a 95% CI of [−0.7, +8.5], so its deltas are drawn without verdict colour. Below it, separately labelled, the synthetic demonstration.
1. **Synthetic comparison** — baseline `support:v1` → candidate `support:v2`: `IMPROVEMENT`, CI gate `PASS`, with the CI drawn against the −5 pt margin.
2. Read **"What changed?"**: *v2 is +50 pts overall (19 cases improved, 3 regressed) — but `address` cases fell 11 pts*.
3. **Compare → case** `sup-17-address-unit-apt`: the diff shows v2 passes `city: "Apt 5"` instead of `"Sollund"`. A localized regression hiding inside an overall win.
4. **Judges**: the strict judge's metrics pass (`ADMITTED ON DEMONSTRATION LABELS — not release-eligible`, because the reference labels are synthetic), the lenient one is `NOT CALIBRATED — diagnostic only`; κ, FPR (with a Wilson upper bound) and a confusion matrix are shown.
5. **CI / Release Gates**: pass, *inconclusive* (30 cases < the production minimum of 50), *invalid* (different dataset hash), and gates **blocked because the judge is not release-eligible** (the strict judge is refused too: its labels are synthetic).

| Compare: decision, CI, margin, validity | Case diff: the regression, exactly |
|---|---|
| ![Compare](docs/images/compare.png) | ![Case diff](docs/images/case-diff.png) |

| Trace explorer (OTel GenAI spans) | Judge calibration |
|---|---|
| ![Trace](docs/images/trace.png) | ![Judge calibration](docs/images/judge-calibration.png) |

| Real-model comparison (Experiment 001, held-out) | Failure analysis |
|---|---|
| ![Live comparison](docs/images/compare-live-heldout.png) | ![Failures](docs/images/failures.png) |

| CI release gates | Mobile (390px) |
|---|---|
| ![Gates](docs/images/gates.png) | ![Mobile](docs/images/experiments-live-mobile.png) |

The interface identity, tokens and chart conventions are documented in [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md); the pre-redesign screenshots are kept in `docs/images/before/` for comparison. All screenshots are captured from the running, seeded application (`make screenshots`).

## Core features

- **Separate scoring layers** — outcome · trajectory · component/tool · policy/safety (+ informational diagnostics). A case passes only if *all gating assertions* pass. No blended "AI score".
- **24 deterministic assertions** with structured evidence (`expected / actual / evidence / severity`): output, tool-call, sequence, argument-match, budgets, state, command exit, file diff, path-safe file checks, **URL grounding**.
- **Statuses that mean something** — `passed · failed · execution_error · invalid · skipped`. Infrastructure failures never count as wrong answers.
- **Statistics engine** — Wilson intervals, clustered paired bootstrap over *cases*, McNemar (diagnostic), `pass^k` (reliability) vs `pass@k` (capability) over an explicit eligible cohort, flaky-case detection, one-sided non-inferiority margin, end-to-end sensitivity analysis for selective missingness.
- **Five verdicts** — improvement · no meaningful regression · regression · **inconclusive** · **invalid comparison** (manifest/provenance mismatch, per declared change *intent*; synthetic vs live can never be compared).
- **LLM-judge calibration** — judge identity includes model, prompt and generation config; admission policy (≥50 items, ≥10/class, κ ≥ 0.6, FPR ≤ 5%, FPR Wilson upper bound ≤ 10%) with a release scope; synthetic labels give *demonstration* eligibility only; the gate refuses non-eligible judges.
- **Human annotation UI** (demo labels are synthetic) — blind items, pass/fail/skip, progress, agreement, disagreement queue; **public handles are untrusted** (never evidence); trusted annotation is an authenticated, non-public workflow.
- **OpenTelemetry traces** (current GenAI semantic conventions behind one mapping module), redaction before storage/export, optional OTLP → Phoenix.
- **Systems under test** — three scripted reference systems (support, research on a real **LangGraph** graph over a **frozen MCP web**, coding with real unit tests; a 15-case red-team suite) **and a live LLM research agent** run through the same pipeline via an agent registry.
- **Frozen, pinned agent versions** and **published (hashed) datasets**; CI fails if a published version changes.
- **Trace → case distillation**, failure taxonomy (19 root causes), deterministic failure clustering.
- **Job queue on Postgres/SQLite** (no Redis) with **leases, an independent heartbeat and fencing**; idempotent seeding, health/readiness, structured logs, typed OpenAPI.
- **Interoperability** — export a dataset to / ingest a log from **Inspect AI**.

## Architecture

![Architecture](docs/images/architecture.svg)

Source: [`docs/architecture.mmd`](docs/architecture.mmd) · details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## The demo story (synthetic fixture evidence, seed `20260601`, 3 samples/case)

n = non-error samples (cases × 3 minus execution errors).

| Suite | Cases | v1 task success | v2 task success | Gate |
|---|---|---|---|---|
| Support | 30 | 38.9 % (CI 29–49) | 88.9 % (CI 81–94) | pass (policy `demo-20`); **inconclusive** under `production` (30 < 50 cases) |
| Research (LangGraph v2) | 20 | 45.6 % | 91.2 % | **gate FAILS: the judge-gated criterion uses a judge that is not release-eligible** (synthetic labels, *demonstration* scope) — the comparison itself is an improvement; the lenient-judge variant fails the same way |
| Coding | 10 | 48.3 % | 90.0 % | **inconclusive** (10 cases) |
| Red team | 15 | 13.3 % | 100 % | pass (`demo-10`) |

Also seeded on purpose: one **invalid** comparison (draft dataset with a different hash), prompt-injection failures, an
**execution error** (MCP server down) that is *not* counted as a quality failure, a failed and an admitted calibration, and
synthetic annotators with disagreements. Do not read these as claims about real models.

## Quick start

```bash
git clone <repo> && cd agent-reliability-studio
make setup           # uv (Python 3.13) + npm (Node >= 22). Installs deps, applies migrations
make demo            # seed + run
```

- **Zero-key demo:** no environment variables needed. `DEMO_MODE=true` makes the app read-only.
- **Local with live runs:** `cp .env.example .env`, set `DEMO_MODE=false` and `ADMIN_TOKEN`, run `ars worker` beside `ars serve`, then `POST /api/runs` (send `X-Admin-Token`) or `ars eval run`.
- **Live LLM agent (operator only):** with your own authenticated Claude Code CLI (no key is read; set `ARS_CLAUDE_BIN` if `claude` is not on PATH): `ars eval run --agent 'live:research:v1?model=haiku' --dataset research-live-dev:v1 --samples 3 --budget-usd 8`. Costs are an API-equivalent *estimate*, never money paid; the model allowlist, per-sample budget and timeout are clamped server-side (the run-level `--budget-usd` is operator-chosen). The older `LiteLLMAdapter` / `ClaudeCodeAdapter` remain optional and were **not** exercised against live providers here.
- **Docker (Postgres + API + web):** `docker compose up --build` → <http://localhost:3000>. Optional Phoenix mirror: `docker compose --profile observability up`.
- **Deploy:** [`render.yaml`](render.yaml) (free-tier-compatible blueprint; not deployed). No live URL is claimed here.

### CLI

```bash
ars demo seed && ars demo verify
ars dataset validate datasets/support/v1.yaml        # schema + hash; published datasets are frozen
ars eval run --agent support:v2 --dataset support:v1 --samples 3
ars eval compare --baseline RUN_A --candidate RUN_B --policy demo-20 --intent agent_change   # strict + --release by default; exit 0 pass | 1 regression | 2 invalid | 3 inconclusive or not release-eligible (--diagnostic never authorizes)
ars eval diff RUN_A RUN_B                            # trajectory + outcome diff per case
ars judge calibrate --judge keyword-strict-v1        # CALIBRATED / NOT CALIBRATED (exit 1)
ars traces distill RUN_ID --out datasets/candidates/   # candidate cases, never auto-promoted
python scripts/check_pins.py                         # frozen agent versions intact?
```

## Evaluation methodology (short)

1. **Deterministic checks first**; a judge only where meaning matters, never alone for safety.
2. **Validate the comparison** (same dataset hash, fixture, samples/case, judge, model; complete runs) before computing anything.
3. **Bootstrap cases, not samples**; apply a practical margin; "not significant" ≠ "equivalent".
4. **Calibrate every judge** against reference labels; the gate refuses an unadmitted one.

Full detail and limits: [`docs/EVAL_METHODOLOGY.md`](docs/EVAL_METHODOLOGY.md). A plain-language study guide: [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md).

## CI release gate (and the evidence that it works)

`.github/workflows/eval-gate.yml` (trigger: `pull_request`, **never** `pull_request_target`) measures baseline and candidate with the **trusted base branch's evaluator,
datasets, fixtures and scripts**; only the agent package comes from the PR. Pins are read from the **git baseline** (fail closed): published versions cannot be removed,
rewritten or un-frozen, new versions need a matching hash and evidence, and changes to shared behaviour code must be re-measured. Evaluator changes get a separate known-answer
validation job. Actions are pinned to commit SHAs (Node 24). No secrets, no model credentials; thresholds are never relaxed to turn CI green.

Proven on GitHub with four disposable PRs ([details and artifacts](docs/CI.md)): a **compatible** candidate reaches the real comparison and passes
([run](https://github.com/errno404/agent-reliability-studio/actions/runs/45522330283)); a **deliberately regressed** one is rejected
([run](https://github.com/errno404/agent-reliability-studio/actions/runs/45522334340)); an **invalid** comparison (undeclared model change) is rejected
([run](https://github.com/errno404/agent-reliability-studio/actions/runs/45522338959)); an **edit of a frozen version with a rewritten pin** is rejected
([run](https://github.com/errno404/agent-reliability-studio/actions/runs/45522337133)). **Honest limit:** PR agent code still shares a Python process with the evaluator, so independent human review
(CODEOWNERS + branch protection — an *owner action*, documented) is the real control.

## Project structure

```
packages/evalcore/     framework-agnostic evaluation core (assertions, stats, calibration, judge, tracing, adapters)
packages/demo_agents/  frozen systems: support · research (LangGraph v2) · coding · live_research (real LLM) (+ PINS.md each)
mcp/fixture_web/       frozen synthetic web served over MCP (official SDK)
services/api/          FastAPI · SQLAlchemy · Alembic · worker queue · `ars` CLI · seed
apps/web/              Next.js dashboard (9 pages + annotation) · vitest · Playwright
datasets/ fixtures/    versioned, hashed evidence (scripts/gen_datasets.py, scripts/gen_live_research.py)
evidence/              published, sanitized experiment and CI-proof evidence
integrations/          Inspect AI (export + ingest) · Phoenix/OTLP
infra/ .github/        Dockerfiles · CI + eval-gate workflows · render.yaml
docs/                  ARCHITECTURE · DESIGN_SYSTEM · EVAL_METHODOLOGY · SECURITY · CI · DEMO · LEARNING_GUIDE · INTERVIEW_GUIDE · EVALUATOR_CASE_STUDY · experiments/ · adr/
```

## Technology choices

Python 3.13 + `uv`; FastAPI/Pydantic v2/SQLAlchemy 2/Alembic; PostgreSQL (canonical) with SQLite for zero-setup; Typer; OpenTelemetry;
official MCP SDK; LangGraph; LiteLLM (optional). Next.js 16 / React 19 / Tailwind 4 / Recharts / TanStack Table; Playwright +
Vitest. Why each: [`docs/adr/`](docs/adr).

## Security boundaries (full detail: [`docs/SECURITY.md`](docs/SECURITY.md))

Public demo = read-only synthetic data plus published evidence: no live LLM runs, no shell, no coding execution, anonymous annotation stored as **untrusted**. Live execution is
operator-only (admin token, clamped model/budget/timeout; uses your own CLI login — no credentials are read). Redaction runs before anything is stored or exported
(canary-tested across every table and endpoint). **The coding-agent execution path is not a sandbox** (validated commands, path/symlink checks, rlimits, scrubbed env — but no network or
filesystem isolation): admin-only, off by default, never expose it.

## Deployment

Not deployed; **no URL is claimed.** `render.yaml` is a free-tier-compatible blueprint (checked against Render's docs on 2026-11-24: private services have no free tier, free Postgres expires after
30 days, free web services spin down after 15 idle minutes). I did not create any Render resource; what remains is for the owner to connect the repo in Render's dashboard, and the
documented free types should cost nothing (I could not verify paid-plan prices from the docs I fetched, so none are quoted). Docker Compose (Postgres + API + web) was validated locally.

## Known limitations

- Demo suites are **scripted stand-ins**; their numbers prove the machinery, not model quality. The only real-model evidence is experiment 001: **one model, one harness, one author, 51 held-out cases × 3 trials, a benchmark near its ceiling** — it detects regressions larger than ~5 points, not small gains.
- Datasets are small, so intervals are wide; the `production` policy wants ≥ 50 independent cases.
- Several scoring checks (non-answers, ambiguity, unofficial-source hedges) are keyword-based; see the [evaluator case study](docs/EVALUATOR_CASE_STUDY.md) — a naive lexical check had 60% false passes on its templated items, and my better scorer dropped to 75% on a stress set. Nothing is human-adjudicated.
- Calibration labels are synthetic fixture labels (*demonstration* eligibility only). No real LLM judge is admitted to gate anything.
- Worker leases are single-database (no distributed-consensus claim). Rate limiters are per-process.
- Latency in the demo is a virtual clock; cost is an API-equivalent estimate, never money paid.

## Roadmap

A subprocess/container boundary between scorer and agent under test; real LLM judge calibrated on human labels (the annotation workflow exists); a harder, larger benchmark; more models and seeds; more adapters (OpenAI Agents, Google ADK).

## Attribution

Concepts were informed by [cryer/agent-eval](https://github.com/cryer/agent-eval) and
[anapsousa/agent-reliability-lab](https://github.com/anapsousa/agent-reliability-lab) (both MIT). **No code was copied**; see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). MIT licensed.
