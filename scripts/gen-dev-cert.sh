#!/usr/bin/env bash
#
#  Generate the self-signed dev certificate nginx needs in order to start.
#  Idempotent — does nothing if a cert and key are already in place.
#
#  docker-compose.yml bind-mounts certificates/web_certificates/ into nginx
#  at /www/certs/, and .env.example points CERT_FILENAME / KEY_FILENAME at
#  the two files written here. Only .gitkeep is tracked in that directory, so
#  a fresh checkout has no cert at all and nginx exits with "cannot load
#  certificate" long before its healthcheck could pass. Anything that brings
#  the stack up from a clean tree has to call this first.
#
#  Real deployments replace these with a proper cert (Let's Encrypt, corp CA)
#  through those same two variables — see .env.example.

set -euo pipefail

# Anchor to the repo top-level, same as the other scripts here: this also
# runs on deploy targets that were rsync'd without a `.git` directory.
cd "$(cd "$(dirname "$0")/.." && pwd)"

cert_dir="certificates/web_certificates"
cert_file="${cert_dir}/iris_dev_cert.pem"
key_file="${cert_dir}/iris_dev_key.pem"

if [ -f "${cert_file}" ] && [ -f "${key_file}" ]; then
    exit 0
fi

mkdir -p "${cert_dir}"

# CN=iris.local with localhost in the SANs: the e2e suite drives
# https://localhost, and operators following the README use a hostname.
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
    -keyout "${key_file}" -out "${cert_file}" \
    -subj "/CN=iris.local" \
    -addext "subjectAltName=DNS:localhost,DNS:iris.local,IP:127.0.0.1" \
    >/dev/null 2>&1
chmod 600 "${key_file}"

echo "[gen-dev-cert] generated self-signed dev cert at ${cert_file} (365 days)"
