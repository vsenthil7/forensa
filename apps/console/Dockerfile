# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS deps
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
WORKDIR /repo
COPY pnpm-workspace.yaml ./
COPY apps/console/package.json apps/console/
RUN cd apps/console && pnpm install --no-frozen-lockfile

FROM node:22-alpine AS builder
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/console/node_modules ./apps/console/node_modules
COPY pnpm-workspace.yaml ./
COPY apps/console ./apps/console
RUN cd apps/console && pnpm exec next build

FROM node:22-alpine AS runtime
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S forensa && adduser -S forensa -G forensa
WORKDIR /app
COPY --from=builder --chown=forensa:forensa /repo/apps/console/.next/standalone ./
COPY --from=builder --chown=forensa:forensa /repo/apps/console/.next/static ./apps/console/.next/static
COPY --from=builder --chown=forensa:forensa /repo/apps/console/public ./apps/console/public
USER forensa
EXPOSE 3000
CMD ["node", "apps/console/server.js"]
