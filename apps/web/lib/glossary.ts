export interface Term { term: string; short: string; why: string }

/** Plain-language definitions used by the Methodology page and inline help. */
export const GLOSSARY: Term[] = [
  { term: "Golden dataset", short: "A versioned, hashed set of test cases with expected behaviour. Never edited once published.", why: "If the test set can quietly change, a score change might just be the test changing." },
  { term: "Trace", short: "The recorded timeline of one agent run: every model call and tool call, with timing, tokens and errors.", why: "Final answers can look right while the path was wrong. The trace is the evidence." },
  { term: "Span", short: "One timed step inside a trace (an agent run, a model call, a tool call). Spans nest like a tree.", why: "Lets you see where time and tokens went, and which step failed." },
  { term: "Trajectory", short: "The ordered list of tools an agent called, e.g. lookup_order → check_refund_eligibility → issue_refund.", why: "Two runs can end the same way via very different (and unequally safe) paths." },
  { term: "Deterministic evaluator", short: "A rule-based check with a yes/no answer: tool called, argument equals X, file unchanged, budget respected.", why: "Cheap, reproducible and not itself a model, so we use it first and for anything safety-critical." },
  { term: "LLM judge", short: "A model that grades free-text output against a rubric, one narrow dimension at a time.", why: "Only needed where meaning matters. It is itself a model, so it must be measured." },
  { term: "Calibration", short: "Running a judge on items with known reference labels and checking how often it agrees.", why: "An uncalibrated judge is a guess. Only an admitted judge may affect a release decision." },
  { term: "Cohen's kappa", short: "Agreement between two raters beyond what chance alone would give. 0 = chance, 1 = perfect.", why: "Raw accuracy flatters a judge when one class dominates; kappa does not." },
  { term: "False positive", short: "The judge says pass but the reference says fail.", why: "A lenient judge ships bad behaviour, so the admission policy caps this rate." },
  { term: "pass@k", short: "Fraction of tasks that pass at least once in k attempts.", why: "Measures capability: can the agent ever do it?" },
  { term: "pass^k", short: "Fraction of tasks that pass every one of k attempts.", why: "Measures reliability: can you depend on it every time? Always ≤ single-run pass rate." },
  { term: "Confidence interval", short: "The range of true pass-rate differences the data is consistent with, found by resampling cases.", why: "A bare number hides uncertainty; the interval is how sure we are." },
  { term: "Non-inferiority margin", short: "How much worse the candidate may be and still be acceptable (e.g. 5 points).", why: "'Not significantly worse' is not 'equivalent'. The margin makes 'acceptable' explicit." },
  { term: "Regression gate", short: "A release check that compares candidate to baseline and blocks on regression, invalid or inconclusive evidence.", why: "Turns 'seems fine' into a repeatable decision with a recorded reason." },
];
