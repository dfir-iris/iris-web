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
# operator setup. Real deployments should replace these with a proper
# cert (Let's Encrypt, corp CA, etc.) — see .env.example for the
# CERT_FILENAME / KEY_FILENAME knobs.
cert_dir="certificates/web_certificates"
cert_file="${cert_dir}/iris_dev_cert.pem"
key_file="${cert_dir}/iris_dev_key.pem"
if [ ! -f "${cert_file}" ] || [ ! -f "${key_file}" ]; then
    mkdir -p "${cert_dir}"
    openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
        -keyout "${key_file}" -out "${cert_file}" \
        -subj "/CN=iris.local" \
        -addext "subjectAltName=DNS:localhost,DNS:iris.local,IP:127.0.0.1" \
        >/dev/null 2>&1
    chmod 600 "${key_file}"
    echo "[dev-up] generated self-signed dev cert at ${cert_file} (365 days)"
fi

docker compose \
    -f docker-compose.yml \
    -f docker-compose.build.yml \
    up -d --build "$@"
