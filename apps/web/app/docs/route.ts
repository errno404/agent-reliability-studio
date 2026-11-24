import { proxy } from "@/lib/proxy";

export const dynamic = "force-dynamic";
export const GET = (req: Request) => proxy(req, "/docs");
