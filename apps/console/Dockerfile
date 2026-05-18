# syntax=docker/dockerfile:1.7
#
# CP9.61 - rewrote console Dockerfile for compose stack.
# Previous bug: separate deps stage installed into apps/console/node_modules
# but the builder copy didn't preserve workspace hoisted layout, so
# `pnpm exec next build` failed to resolve `next` binary.
# Fix: single builder stage installs from workspace root using
# pnpm install --filter @forensa/console.

FROM node:22-alpine AS builder
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
WORKDIR /repo

# Copy workspace files first so install layer caches well
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json* ./
COPY apps/console/package.json apps/console/

# Install dependencies for the console workspace
RUN pnpm install --filter @forensa/console --frozen-lockfile=false

# Now copy source and build
COPY apps/console ./apps/console

# Build the standalone Next.js output (next.config.mjs has output: 'standalone')
RUN cd apps/console && pnpm exec next build

# --------------------------------------------------------------- runtime
FROM node:22-alpine AS runtime
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S forensa && adduser -S forensa -G forensa
WORKDIR /app

# Next standalone output bundles server.js + minimal node_modules at this path
COPY --from=builder --chown=forensa:forensa /repo/apps/console/.next/standalone ./
COPY --from=builder --chown=forensa:forensa /repo/apps/console/.next/static ./apps/console/.next/static
COPY --from=builder --chown=forensa:forensa /repo/apps/console/public ./apps/console/public

USER forensa
EXPOSE 3000
CMD ["node", "apps/console/server.js"]
