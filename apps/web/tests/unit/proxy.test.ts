import { describe, expect, it } from "vitest";
import { forwardedClient } from "@/lib/proxy";

const h = (xff?: string) => new Headers(xff ? { "x-forwarded-for": xff } : {});

describe("forwardedClient (rate-limit identity)", () => {
  it("with no trusted edge, a client-supplied X-Forwarded-For is never used", () => {
    expect(forwardedClient(h("6.6.6.6"), 0)).toBeNull();
    expect(forwardedClient(h("1.1.1.1, 6.6.6.6"), 0)).toBeNull();
  });
  it("with one trusted edge, uses the LAST entry (appended by the edge), not client-controlled earlier entries", () => {
    expect(forwardedClient(h("6.6.6.6, 203.0.113.7"), 1)).toBe("203.0.113.7");
  });
  it("with two trusted hops, selects the second from the end", () => {
    expect(forwardedClient(h("6.6.6.6, 203.0.113.7, 10.0.0.2"), 2)).toBe("203.0.113.7");
  });
  it("rejects missing, short or malformed values", () => {
    expect(forwardedClient(h(), 1)).toBeNull();
    expect(forwardedClient(h("203.0.113.7"), 2)).toBeNull();
    expect(forwardedClient(h("evil; x-admin=1"), 1)).toBeNull();
    expect(forwardedClient(h("1.1.1.1"), Number.NaN)).toBeNull();
  });
});
