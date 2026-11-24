import { proxy } from "@/lib/proxy";

export const dynamic = "force-dynamic";
type Ctx = { params: Promise<{ path: string[] }> };

// Only paths under /api are forwarded (the upstream base is fixed by API_URL); ".." segments are rejected.
async function handle(req: Request, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;
  if (path.some((p) => p === ".." || p === "." || p.includes("\\"))) return Response.json({ detail: "bad path" }, { status: 400 });
  return proxy(req, `/api/${path.map(encodeURIComponent).join("/")}`);
}
export const GET = handle;
export const POST = handle;
