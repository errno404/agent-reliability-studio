/** Runtime reverse proxy to the FastAPI service. `API_URL` is read per request, so one build runs anywhere. */
const HOP_BY_HOP = new Set(["connection", "keep-alive", "transfer-encoding", "te", "upgrade", "host", "content-length", "accept-encoding"]);
// Client-supplied forwarding headers are untrusted: drop them all; re-assert one address only if a trusted edge exists.
const FORWARDING = /^(x-forwarded-.*|forwarded|x-real-ip|x-client-ip|cf-connecting-ip|true-client-ip)$/i;

/**
 * Client address to assert to the API, or null.
 *
 * `hops` = number of trusted edge proxies in front of this app (env TRUSTED_PROXY_HOPS, default 0).
 * With 0 trusted hops EVERY client-supplied forwarding header is untrusted and dropped (the API then sees this
 * service's address, so all users share one rate-limit bucket: safe, if coarse). With N >= 1 the address appended by
 * the outermost trusted edge is the Nth entry from the END of X-Forwarded-For; earlier entries are client-controlled.
 */
export function forwardedClient(headers: Headers, hops: number): string | null {
  if (!Number.isInteger(hops) || hops < 1) return null;
  const parts = (headers.get("x-forwarded-for") ?? "").split(",").map((p) => p.trim()).filter(Boolean);
  if (parts.length < hops) return null;
  const candidate = parts[parts.length - hops] ?? "";
  return /^[0-9a-fA-F:.]{3,45}$/.test(candidate) ? candidate : null;
}

export async function proxy(req: Request, upstreamPath: string): Promise<Response> {
  const base = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const url = new URL(req.url);
  const target = `${base}${upstreamPath}${url.search}`;
  const headers = new Headers();
  req.headers.forEach((v, k) => { if (!HOP_BY_HOP.has(k.toLowerCase()) && !FORWARDING.test(k)) headers.set(k, v); });
  const client = forwardedClient(req.headers, Number(process.env.TRUSTED_PROXY_HOPS ?? 0));
  if (client) headers.set("x-forwarded-for", client);
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  try {
    const res = await fetch(target, { method: req.method, headers, body: hasBody ? await req.arrayBuffer() : undefined, cache: "no-store", redirect: "manual" });
    const out = new Headers();
    res.headers.forEach((v, k) => { if (!HOP_BY_HOP.has(k.toLowerCase()) && k.toLowerCase() !== "content-encoding") out.set(k, v); });
    return new Response(res.body, { status: res.status, headers: out });
  } catch {
    return Response.json({ detail: "API unreachable" }, { status: 502 });
  }
}
