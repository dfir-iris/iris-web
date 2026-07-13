# Multi-stage build for the SvelteKit new-UI frontend.
#
# Build context is the iris-frontend repo root, NOT this directory —
# see `context:` in docker-compose.new-ui.yml.
#
#   Stage 1 (`builder`)  — install full deps, run `npm run build`.
#   Stage 2 (runtime)    — copy the build output + prod node_modules,
#                           start `node build` as a non-root user.
#
# Pin the major-version of node so dev and prod use the same runtime.

ARG NODE_VERSION=23-alpine

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS builder

WORKDIR /app

# `npm ci` needs both lockfile + package.json before any source is copied
# so the install layer caches independently of source edits.
COPY package.json package-lock.json ./

RUN npm ci --no-audit --no-fund

# Now bring in the rest of the source and produce the production build.
# SvelteKit's adapter-node writes the runnable server bundle to /app/build.
COPY . .

RUN npm run build

# Strip dev dependencies so the runtime image only carries what `node
# build` needs at runtime.
RUN npm prune --omit=dev


# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS runtime

# Drop privileges. The node image ships a `node` user (uid 1000) we can
# reuse — owns nothing in /app so we chown the copied artefacts.
WORKDIR /app

COPY --from=builder --chown=node:node /app/build         ./build
COPY --from=builder --chown=node:node /app/node_modules  ./node_modules
COPY --from=builder --chown=node:node /app/package.json  ./package.json

USER node

ENV NODE_ENV=production
ENV PORT=5173
ENV HOST=0.0.0.0

EXPOSE 5173

# SvelteKit's adapter-node produces a server entry at build/index.js;
# launching `node build` runs it.
CMD ["node", "build"]
