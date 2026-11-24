# syntax=docker/dockerfile:1.7
FROM node:22-slim AS deps
WORKDIR /repo/apps/web
COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /repo/apps/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /repo/apps/web/node_modules ./node_modules
COPY apps/web ./
RUN npm run build

FROM node:22-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 ars
WORKDIR /repo
# standalone output keeps the monorepo-relative layout (outputFileTracingRoot = repo root)
COPY --from=build --chown=ars /repo/apps/web/.next/standalone ./
COPY --from=build --chown=ars /repo/apps/web/.next/static ./apps/web/.next/static
USER ars
EXPOSE 3000
# API_URL is read at RUNTIME by the proxy route handler (not baked into the image).
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 CMD curl -fsS http://127.0.0.1:${PORT}/ >/dev/null || exit 1
CMD ["node", "apps/web/server.js"]
