# Evaluator validation case study: how a naive lexical check fails, and what stronger deterministic scoring fixes

> **What this is and is not.** 64 templated outputs plus a 12-phrasing stress set, all **author-written with author labels**
> (`label_source: synthetic_fixture`). It is **not human adjudication**, **not a prevalence estimate** and not a claim that evaluator
> C is "good": it is a demonstration of *failure classes*, with the evaluator I designed scored on items I also wrote (optimistic by
> construction). Reproduce: `python scripts/evaluator_case_study.py`. Raw results: `evidence/evaluator-study/results.json`.

## Setup
Eight invented facts (e.g. "the Harlow Rail fleet has 62 trains"; decoy figure 70) x eight output classes = 64 items; 24 should pass
and 40 should fail. Three evaluators:

| | Evaluator | Idea |
|---|---|---|
| A | naive lexical | pass iff the expected figure appears anywhere (what a quick `output_contains` does) |
| B | keyword judge | `evalcore.judge.HeuristicJudge` — the repository's synthetic MUST / MUST_NOT token-coverage judge |
| C | stronger deterministic | extract the figures the output **asserts**: boundary-safe digits and spelled-out numbers, attribute-keyword proximity, negation and attribution scopes, forbidden-figure check, completeness of every required fact |

## Results (64 templated items)
| Evaluator | Accuracy | False passes (should fail) | False fails (should pass) |
|---|---|---|---|
| A naive lexical | 50.0% (32/64) | **24 / 40 = 60%** (Wilson 95%: 44.6-73.7%) | 8 / 24 |
| B keyword judge | 62.5% (40/64) | 8 / 40 = 20% (10.5-34.8%) | **16 / 24 = 67%** |
| C stronger deterministic | 100% (64/64) | 0 / 40 (upper bound **8.8%**) | 0 / 24 |

Correct decisions per output class (8 items each):

| Class (truth) | A | B | C |
|---|---|---|---|
| valid (pass) | 8 | 8 | 8 |
| valid, spelled out: "sixty-two trains" (pass) | **0** | **0** | 8 |
| valid, refutes a decoy: "a blog claims 70, but the official figure is 62" (pass) | 8 | **0** | 8 |
| unsupported figure (fail) | 8 | 8 | 8 |
| negated correct figure: "it is not true that ... 62; the real number is 70" (fail) | **0** | 8 | 8 |
| misleading keyword overlap: right number, wrong attribute (fail) | **0** | **0** | 8 |
| incomplete answer to a two-part question (fail) | **0** | 8 | 8 |
| irrelevant but plausible (fail) | 8 | 8 | 8 |

Concrete errors:
* **A false pass (negation):** "It is not true that Harlow Rail has 62 trains; the real number is 70." — contains `62`, so it passes.
* **A false pass (overlap):** "Harlow Rail serves 62 stations ... The fleet figure was not stated in the sources I checked." — right digits, wrong attribute, and an explicit non-answer.
* **A false pass (incomplete):** "Harlow Rail has 62 trains." — the question asked for fleet size *and* top speed.
* **B false fail (spelled-out):** "The count for Harlow Rail is sixty-two trains." — token coverage misses `62`.
* **B false fail (refutation):** "A fan blog claims 70 trains, but the official figure is 62." — a forbidden-phrase hit sinks a correct, well-sourced answer.

## Stress set: written after C was frozen, never used to adjust it (12 phrasings, same question)
| Evaluator | Accuracy | Errors |
|---|---|---|
| A | 5/12 | 6 false passes (retraction, `620`, `62.5`, sub-population, non-answer, stale figure), 1 false fail |
| B | 6/12 | `620`, `62.5`, "62 of the trains are electric" pass; "Not 70 - ... 62", "will grow to 70 ... today it has 62", "Sixty two" fail |
| C | **9/12 (75%)** | false fail: "Not 70 - the fleet is 62 trains." (negation scope bleeds onto the truth); false fail: "The fleet will grow to 70 trains next year; today it has 62." (a future decoy counts as asserted); **false pass:** "62 of the trains in the fleet are electric." (figure belongs to a sub-population; proximity cannot tell) |

C's 100% on templated items collapses to 75% on phrasings it was not built around. That gap is the lesson: pattern-based scoring is
brittle at the edges, and templated author-made suites overstate it.

## What this changes in the project
* The lexical failure modes above are exactly why live experiment 001 scores the **asserted figure with boundary-safe regexes**,
  adds URL-grounding checks, and **never** asserts "the answer must not mention X" (two pilot false negatives came from that).
* No LLM judge gates anything in experiment 001. A real judge would need human-labelled calibration first
  (`docs/EVAL_METHODOLOGY.md`: synthetic labels give release scope "demonstration" only; FPR is reported with a Wilson upper bound).
* The non-answer checks in experiment 001 (unanswerable, ambiguous, unofficial-source hedges) are keyword-based and subject to
  the same weaknesses; they are listed as limitations there.

## Annotation workflow for the owner (turning this into real evidence)
1. Load the set into a database: `uv run python -m app.cli judge calibrate --judge keyword-strict-v1 --set datasets/evaluator-study/annotation-v1.yaml`
   (this syncs the set under the name `evaluator-study` and also reports how the synthetic keyword judge does on it; the 64 items are in
   calibration-set format with `label_source: synthetic_fixture`, i.e. the AUTHOR's labels).
2. Label **blind** (the UI/`GET /api/annotation/next?set_name=evaluator-study` returns input, output and rubric, never the author label):
   - *Public/untrusted* labels (`POST /api/annotation`) are stored as `public_untrusted` and never count as evidence.
   - *Trusted* labels need an authenticated session: run the API with `DEMO_MODE=false` and an `ADMIN_TOKEN`, then `POST /api/annotation/trusted`
     (`X-Admin-Token`). Use at least two independent annotators; disagreements go to `POST /api/annotation/trusted/adjudicate`.
3. Compare: agreement kappa (`GET /api/annotation/summary`), then re-run `scripts/evaluator_case_study.py` against the human labels. Only labels
   from `human`/`adjudicated` sources can ever move a judge's release eligibility beyond `demonstration`.
4. Until that exists, nothing in this repository claims human adjudication.
