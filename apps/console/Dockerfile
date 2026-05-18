# syntax=docker/dockerfile:1.7
#
# CP9.61 - dev-mode console Dockerfile for compose stack.
# This is the DEV target. For production builds (Phase 12+), a
# separate Dockerfile with `output: 'standalone'` + multi-stage
# builder will be used. For now compose runs dev mode which is the
# canonical hackathon-to-Monday-demo path.
#
# Previous bug (resolved): the multi-stage builder tried to copy
# node_modules between stages, but pnpm workspace symlinks broke
# across the COPY boundary. Single-stage avoids the issue entirely.

FROM node:22-alpine AS dev
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
WORKDIR /repo

# Install deps at workspace root (pnpm handles hoisting + symlinks)
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/console/package.json apps/console/
RUN pnpm install --frozen-lockfile=false

# Copy source (compose mounts these as volumes for hot-reload)
COPY apps/console ./apps/console

WORKDIR /repo/apps/console
ENV NODE_ENV=development PORT=3000 HOSTNAME=0.0.0.0
EXPOSE 3000
CMD ["pnpm", "exec", "next", "dev", "-p", "3000"]
