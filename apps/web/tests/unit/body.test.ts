import { describe, expect, it } from "vitest";
import { readLimited } from "@/lib/proxy";

const chunked = (parts: string[]) => new Request("http://x.test/", {
  method: "POST", duplex: "half",
  body: new ReadableStream({ start(c) { parts.forEach((p) => c.enqueue(new TextEncoder().encode(p))); c.close(); } }),
} as RequestInit);

describe("readLimited", () => {
  it("returns small bodies intact", async () => {
    expect(new TextDecoder().decode((await readLimited(chunked(["ab", "cd"]), 10))!)).toBe("abcd");
  });
  it("rejects an oversized CHUNKED body that sends no Content-Length", async () => {
    expect(await readLimited(chunked(["x".repeat(6), "y".repeat(6)]), 10)).toBeNull();
  });
});
