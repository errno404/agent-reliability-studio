import path from "node:path";
import type { NextConfig } from "next";

// Pin the workspace root to this repo: a stray lockfile in $HOME otherwise makes Next crawl the whole home directory.
const ROOT = path.resolve(process.cwd(), "../..");

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: ROOT,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: { root: ROOT },
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};
export default config;
