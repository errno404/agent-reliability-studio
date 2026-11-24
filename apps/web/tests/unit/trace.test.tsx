import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TraceWaterfall } from "@/components/trace-waterfall";
import type { SpanOut } from "@/lib/types";

const spans: SpanOut[] = [
  { span_id: "a", parent_id: null, name: "invoke_agent support", kind: "agent", start_ms: 0, duration_ms: 800, status: "ok", attributes: { "gen_ai.operation.name": "invoke_agent" } },
  { span_id: "b", parent_id: "a", name: "execute_tool lookup_order", kind: "tool", start_ms: 100, duration_ms: 120, status: "ok", attributes: { "gen_ai.tool.name": "lookup_order", "gen_ai.tool.call.arguments": '{"order_id":"O-5009"}' } },
  { span_id: "c", parent_id: "a", name: "execute_tool update_shipping_address", kind: "tool", start_ms: 300, duration_ms: 90, status: "error", attributes: { "error.type": "tool_error" } },
];

describe("TraceWaterfall", () => {
  it("renders nested spans in tree order and selects a span to show its attributes", () => {
    render(<TraceWaterfall spans={spans} totalMs={800} />);
    const options = screen.getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([expect.stringContaining("invoke_agent"), expect.stringContaining("lookup_order"), expect.stringContaining("update_shipping_address")]);
    fireEvent.click(within(screen.getByRole("listbox")).getByText("execute_tool lookup_order"));
    expect(screen.getByText("gen_ai.tool.call.arguments")).toBeInTheDocument();
    expect(screen.getByText(/O-5009/)).toBeInTheDocument();
  });
  it("flags errored spans", () => {
    render(<TraceWaterfall spans={spans} totalMs={800} />);
    expect(screen.getAllByText("error").length).toBeGreaterThan(0);
  });
  it("states that no reasoning content is recorded", () => {
    render(<TraceWaterfall spans={spans} totalMs={800} />);
    expect(screen.getByText(/no reasoning content is recorded/)).toBeInTheDocument();
  });
});
