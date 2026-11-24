/** Runtime reverse proxy to the FastAPI service. `API_URL` is read per request, so one build runs anywhere. */
const HOP_BY_HOP = new Set(["connection", "keep-alive", "transfer-encoding", "te", "upgrade", "host", "content-length", "accept-encoding"]);

export async function proxy(req: Request, upstreamPath: string): Promise<Response> {
  const base = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const url = new URL(req.url);
  const target = `${base}${upstreamPath}${url.search}`;
  const headers = new Headers();
  req.headers.forEach((v, k) => { if (!HOP_BY_HOP.has(k.toLowerCase())) headers.set(k, v); });
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
