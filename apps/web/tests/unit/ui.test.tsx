import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CiPlot } from "@/components/charts";
import { DecisionBadge, EmptyState, ErrorState, Stat } from "@/components/ui";
import { ApiError } from "@/lib/api";

describe("Stat", () => {
  it("always exposes sample size and confidence interval next to a rate", () => {
    render(<Stat label="Task success" value="88.9%" n={90} ciLo={0.81} ciHi={0.94} />);
    expect(screen.getByText("88.9%")).toBeInTheDocument();
    expect(screen.getByText(/95% CI 81%–94%/)).toBeInTheDocument();
    expect(screen.getByText(/n=90/)).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("distinguishes error kinds instead of showing a generic failure", () => {
    const { rerender } = render(<ErrorState error={new ApiError("network", 0, "x")} />);
    expect(screen.getByText("Backend unreachable")).toBeInTheDocument();
    rerender(<ErrorState error={new ApiError("forbidden", 403, "read-only")} />);
    expect(screen.getByText("Disabled in the public demo")).toBeInTheDocument();
    rerender(<ErrorState error={new ApiError("not_found", 404, "nope")} />);
    expect(screen.getByText("Not found")).toBeInTheDocument();
    rerender(<ErrorState error={new ApiError("conflict", 409, "dup")} />);
    expect(screen.getByText("Already recorded")).toBeInTheDocument();
  });
  it("is announced to assistive tech", () => {
    render(<ErrorState error={new ApiError("server", 500, "boom")} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("DecisionBadge / EmptyState", () => {
  it("renders the comparison verdict text", () => {
    render(<DecisionBadge decision="inconclusive" />);
    expect(screen.getByText("INCONCLUSIVE")).toBeInTheDocument();
  });
  it("renders a helpful empty state", () => {
    render(<EmptyState title="No experiments match these filters">Clear a filter.</EmptyState>);
    expect(screen.getByText("Clear a filter.")).toBeInTheDocument();
  });
});

describe("CiPlot", () => {
  it("describes the interval and margin textually for screen readers", () => {
    render(<CiPlot delta={0.5} lo={0.267} hi={0.722} margin={0.05} />);
    expect(screen.getByRole("img", { name: /Delta 50\.0 points, 95% interval 26\.7 to 72\.2, margin −5/ })).toBeInTheDocument();
  });
});
