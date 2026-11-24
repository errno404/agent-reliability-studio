/** Runtime reverse proxy to the FastAPI service. `API_URL` is read per request, so one build runs anywhere. */
const HOP_BY_HOP = new Set(["connection", "keep-alive", "transfer-encoding", "te", "upgrade", "host", "content-length", "accept-encoding"]);
// Client-supplied forwarding headers are untrusted: drop them all and re-assert a single, edge-appended client address.
const FORWARDING = /^(x-forwarded-.*|forwarded|x-real-ip|x-client-ip|cf-connecting-ip|true-client-ip)$/i;

/** The address appended by the nearest trusted edge proxy = the LAST x-forwarded-for entry (earlier entries are client-controlled). */
function edgeClient(req: Request): string | null {
  const xff = req.headers.get("x-forwarded-for");
  const last = xff?.split(",").pop()?.trim();
  return last && /^[0-9a-fA-F:.]{3,45}$/.test(last) ? last : null;
}

export async function proxy(req: Request, upstreamPath: string): Promise<Response> {
  const base = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const url = new URL(req.url);
  const target = `${base}${upstreamPath}${url.search}`;
  const headers = new Headers();
  req.headers.forEach((v, k) => { if (!HOP_BY_HOP.has(k.toLowerCase()) && !FORWARDING.test(k)) headers.set(k, v); });
  const client = edgeClient(req);
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
