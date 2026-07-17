#!/usr/bin/env bash
#
#  Tail logs from the IRIS stack. Pass service names to filter.

set -euo pipefail

cd "$(cd "$(dirname "$0")/.." && pwd)"

exec docker compose logs -f "$@"
