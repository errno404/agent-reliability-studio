import { describe, expect, it } from "vitest";
import { ci, decisionLabel, decisionTone, ms, pct, pts, statusTone, usd } from "@/lib/format";

describe("format", () => {
  it("formats percentages and handles missing values", () => {
    expect(pct(0.8889)).toBe("88.9%");
    expect(pct(0.5, 0)).toBe("50%");
    expect(pct(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
  });
  it("formats signed point deltas with a true minus sign", () => {
    expect(pts(0.5)).toBe("+50.0 pts");
    expect(pts(-0.024)).toBe("−2.4 pts");
    expect(pts(null)).toBe("—");
  });
  it("formats latency, cost and intervals", () => {
    expect(ms(840)).toBe("840 ms");
    expect(ms(1030)).toBe("1.03 s");
    expect(usd(null)).toBe("—");
    expect(usd(0.0632)).toBe("$0.0632");
    expect(usd(12.5)).toBe("$12.50");
    expect(ci(0.81, 0.94)).toBe("81.0–94.0%");
  });
  it("maps every comparison decision to a distinct tone and label", () => {
    expect(decisionTone("significant_regression")).toBe("bad");
    expect(decisionTone("inconclusive")).toBe("warn");
    expect(decisionTone("invalid")).toBe("info");
    expect(decisionLabel("invalid")).toBe("INVALID COMPARISON");
    expect(decisionLabel("significant_improvement")).toBe("IMPROVEMENT");
  });
  it("never treats an execution error like a failure", () => {
    expect(statusTone("execution_error")).toBe("warn");
    expect(statusTone("failed")).toBe("bad");
  });
});
