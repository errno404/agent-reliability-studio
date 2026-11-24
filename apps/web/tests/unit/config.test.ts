import { afterEach, describe, expect, it } from "vitest";
import { apiBase } from "@/lib/config";

const original = process.env.API_URL;
afterEach(() => { if (original === undefined) delete process.env.API_URL; else process.env.API_URL = original; });

describe("apiBase", () => {
  it("defaults to loopback, accepts a full URL, and adds a scheme to a bare host:port", () => {
    delete process.env.API_URL;
    expect(apiBase()).toBe("http://127.0.0.1:8000");
    process.env.API_URL = "https://api.example.test/";
    expect(apiBase()).toBe("https://api.example.test");
    process.env.API_URL = "ars-api-x1:10000";
    expect(apiBase()).toBe("http://ars-api-x1:10000");
  });
});
