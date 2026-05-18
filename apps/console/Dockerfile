# syntax=docker/dockerfile:1.7
#
# CP9.61 - dev-mode console Dockerfile for compose stack.
#
# Critical: pnpm symlinks in apps/console/node_modules contain absolute
# host paths (Windows paths in dev). If those leak into the image they
# point at non-existent targets and `next dev` fails with MODULE_NOT_FOUND.
# We belt-and-braces this by (a) .dockerignore excluding nested
# node_modules and (b) `rm -rf` any node_modules dir before in-container
# pnpm install.

FROM node:22-alpine AS dev
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
WORKDIR /repo

# Workspace manifests for the install layer (cached unless deps change)
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/console/package.json apps/console/

# Source - in case any leaked node_modules came through, nuke them.
COPY apps/console ./apps/console
RUN find /repo -type d -name node_modules -exec rm -rf {} + || true \
    && find /repo -type l -name next -exec rm -f {} + || true

# Fresh in-container install creates valid Linux symlinks
RUN pnpm install --frozen-lockfile=false

WORKDIR /repo/apps/console
ENV NODE_ENV=development PORT=3000 HOSTNAME=0.0.0.0
EXPOSE 3000
CMD ["pnpm", "exec", "next", "dev", "-p", "3000"]
