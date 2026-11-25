import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KindBadge, LiveNote } from "@/components/ui";
import { annotationTrust, comparisonKind, controlledVariables, kindOf, modeLabel, releaseScope, scopeLabel, splitKinds, wilson } from "@/lib/live";
import type { CalRun, RunOut } from "@/lib/types";

const run = (id: string, kind: string, n = 10) => ({ id, execution_kind: kind, n_samples: n }) as unknown as RunOut;

describe("live vs synthetic are never blended", () => {
  it("splits runs and samples per kind", () => {
    const s = splitKinds([run("a", "synthetic", 10), run("b", "live", 7), run("c", "synthetic", 5)]);
    expect(s).toEqual({ synthetic: { runs: 2, samples: 15 }, live: { runs: 1, samples: 7 } });
  });
  it("derives a comparison's kind from its two runs and flags mixed pairs", () => {
    const rs = [run("a", "live"), run("b", "live"), run("c", "synthetic")];
    expect(comparisonKind({ baseline_run_id: "a", candidate_run_id: "b" }, rs)).toBe("live");
    expect(comparisonKind({ baseline_run_id: "a", candidate_run_id: "c" }, rs)).toBe("mixed");
    expect(kindOf(run("x", "anything-else"))).toBe("synthetic");
  });
  it("labels render and the live note names the controlled environment", () => {
    render(<><KindBadge kind="live" /><KindBadge kind="synthetic" /><KindBadge kind="mixed" /><LiveNote /></>);
    expect(screen.getByText("live model")).toBeInTheDocument();
    expect(screen.getByText("synthetic")).toBeInTheDocument();
    expect(screen.getByText("mixed kinds")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Real LLM behaviour evaluated in a controlled synthetic environment.");
  });
});

describe("comparison intent and mode", () => {
  it("a prompt change varies nothing: model and evaluator are controlled", () => {
    const { varied, controlled } = controlledVariables("prompt_change");
    expect(varied).toEqual([]);
    expect(controlled).toEqual(expect.arrayContaining(["model_resolved", "evaluator_hash", "dataset_hash", "execution_kind"]));
  });
  it("a model change may vary the model but never the dataset or the evaluator", () => {
    const { varied, controlled } = controlledVariables("model_change");
    expect(varied).toContain("model_resolved");
    expect(controlled).not.toContain("model");
    expect(controlled).toEqual(expect.arrayContaining(["dataset_hash", "evaluator_hash"]));
  });
  it("only strict can authorise a release", () => {
    expect(modeLabel("strict", "release-grade evidence").tone).toBe("ok");
    const x = modeLabel("exploratory");
    expect(x.tone).toBe("warn");
    expect(x.text).toMatch(/cannot authorise a release/);
  });
});

describe("calibration uncertainty", () => {
  it("Wilson interval matches known values and handles n=0", () => {
    const [lo, hi] = wilson(0, 40);
    expect(lo).toBe(0);
    expect(hi).toBeCloseTo(0.0877, 3);
    expect(wilson(5, 10)[0]).toBeCloseTo(0.2366, 3);
    expect(wilson(0, 0)).toEqual([0, 1]);
  });
  const cal = (over: Partial<CalRun> = {}) => ({
    admitted: true, reasons: [], reference_sources: { synthetic_fixture: 60 },
    metrics: { n: 60, n_pos: 20, n_neg: 40, tp: 20, fp: 0, tn: 40, fn: 0 }, policy: { min_trusted_items: 50, max_fpr_upper: 0.1 }, ...over,
  }) as unknown as CalRun;
  it("an admitted judge on synthetic labels is DEMONSTRATION only, never release", () => {
    const r = releaseScope(cal());
    expect(r.eligible).toBe(false);
    expect(r.scope).toBe("demonstration");
    expect(r.reasons.join(" ")).toMatch(/0 human\/adjudicated/);
    expect(scopeLabel(r.scope)).toMatch(/cannot authorise a release/);
  });
  it("is release-eligible only with enough trusted labels AND a small FPR upper bound", () => {
    const ok = releaseScope(cal({ reference_sources: { human: 60 }, metrics: { n: 400, n_pos: 200, n_neg: 200, tp: 200, fp: 0, tn: 200, fn: 0 } as CalRun["metrics"] }));
    expect(ok.eligible).toBe(true);
    // 0 false positives out of only 20 negatives: the point estimate is perfect, the 95% upper bound (~16%) is not
    const weak = releaseScope(cal({ reference_sources: { human: 60 }, metrics: { n: 40, n_pos: 20, n_neg: 20, tp: 20, fp: 0, tn: 20, fn: 0 } as CalRun["metrics"] }));
    expect(weak.eligible).toBe(false);
    expect(weak.reasons.join(" ")).toMatch(/upper bound/);
  });
  it("a non-admitted judge is diagnostic; never calibrated is diagnostic", () => {
    expect(releaseScope(cal({ admitted: false })).scope).toBe("diagnostic");
    expect(releaseScope(null).scope).toBe("diagnostic");
  });
});

describe("annotation trust labels", () => {
  it("public handles are untrusted; only authenticated human rows are trusted", () => {
    expect(annotationTrust("public_untrusted")).toMatchObject({ tone: "warn", label: expect.stringMatching(/untrusted/) });
    expect(annotationTrust("human").tone).toBe("ok");
    expect(annotationTrust("synthetic_demo").label).toMatch(/synthetic/);
  });
});
