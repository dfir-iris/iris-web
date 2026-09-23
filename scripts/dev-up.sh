#!/usr/bin/env bash
#
#  Bring up the IRIS stack from local submodule builds (dev mode).
#  For pull-only usage, run `docker compose up -d` directly.

set -euo pipefail

# Anchor to the repo top-level. `git rev-parse` would work in a checkout
# but this script also runs on deploy targets that were rsync'd without
# a `.git` directory — resolve the parent of scripts/ directly.
cd "$(cd "$(dirname "$0")/.." && pwd)"

# Generate a self-signed cert on first run so nginx can start without
# operator setup. Shared with the e2e workflow, which brings the stack up
# from a clean checkout and hits the same missing-cert failure.
./scripts/gen-dev-cert.sh

docker compose \
    -f docker-compose.yml \
    -f docker-compose.build.yml \
    up -d --build "$@"
