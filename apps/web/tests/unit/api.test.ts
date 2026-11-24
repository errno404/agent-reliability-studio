import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());
const respond = (status: number, body: unknown) => vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status }));

describe("api client", () => {
  it.each([[404, "not_found"], [403, "forbidden"], [429, "rate_limited"], [409, "conflict"], [500, "server"], [422, "client"]])("maps HTTP %i to %s", async (status, kind) => {
    respond(status, { detail: "x" });
    await expect(api.meta()).rejects.toMatchObject({ kind, status });
  });
  it("surfaces network failure distinctly", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    await expect(api.meta()).rejects.toBeInstanceOf(ApiError);
    await expect(api.meta()).rejects.toMatchObject({ kind: "network" });
  });
  it("returns typed JSON on success and builds query strings without empty params", async () => {
    const spy = respond(200, { items: [], total: 0, page: 1, page_size: 25 });
    await api.runs({ agent: "support", status: "", page: 2 });
    expect(String(spy.mock.calls[0]![0])).toContain("/api/runs?agent=support&page=2");
  });
});
