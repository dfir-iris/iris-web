#!/usr/bin/env bash
#
#  Bring up the IRIS stack from local submodule builds (dev mode).
#  For pull-only usage, run `docker compose up -d` directly.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

docker compose \
    -f docker-compose.yml \
    -f docker-compose.build.yml \
    up -d --build "$@"
