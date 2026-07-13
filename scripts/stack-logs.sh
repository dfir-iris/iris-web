#!/usr/bin/env bash
#
#  Tail logs from the IRIS stack. Pass service names to filter.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec docker compose logs -f "$@"
