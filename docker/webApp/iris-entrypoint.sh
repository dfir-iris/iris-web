#!/bin/bash

#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.




target=${1-:app}

if [[ -z $LOG_LEVEL ]]; then
  LOG_LEVEL='info'
fi

# ----------------------------------------------------------------------
# Operator-supplied CA bundle install.
#
# Two supported layouts under /etc/iris-ca/ (bind-mounted from
# ./certificates/ca-bundle/ per docker-compose.base.yml):
#
#   1. Legacy — a single concatenated bundle at
#      /etc/iris-ca/extra-ca.crt. Preserved as-is for backward
#      compatibility with existing deployments.
#
#   2. Drop-in — one or more *.crt / *.pem files placed anywhere
#      under /etc/iris-ca/. Each is installed into the OS trust store
#      individually. No manual concatenation with the system roots
#      required — update-ca-certificates ADDS to the store, it does
#      not replace it (unlike REQUESTS_CA_BUNDLE / SSL_CERT_FILE).
#
# Registering CAs at the OS level makes *every* TLS library inside
# the image trust them (requests, urllib3, the oic library, ldap,
# ...). Without this, setting REQUESTS_CA_BUNDLE only fixes the
# `requests` calls — the `oic` library opens its own session that
# ignores the env var and fails on internal CAs at the token
# endpoint.
#
# Idempotent: safe on every boot, tolerates the directory being
# missing or the operator not opting in.
_iris_ca_installed_any=0

if [[ -s /etc/iris-ca/extra-ca.crt ]]; then
  if [[ ! -f /usr/local/share/ca-certificates/iris-extra-ca.crt ]] \
     || ! cmp -s /etc/iris-ca/extra-ca.crt /usr/local/share/ca-certificates/iris-extra-ca.crt; then
    printf "Installing operator CA bundle into system trust store...\n"
    cp /etc/iris-ca/extra-ca.crt /usr/local/share/ca-certificates/iris-extra-ca.crt
    _iris_ca_installed_any=1
  fi
fi

if [[ -d /etc/iris-ca ]]; then
  while IFS= read -r -d '' ca_src; do
    # Skip the legacy single-file bundle — already handled above.
    [[ "${ca_src}" == "/etc/iris-ca/extra-ca.crt" ]] && continue
    # Flatten nested paths into a unique filename so multiple CAs
    # from subdirectories don't collide in the destination dir.
    rel="${ca_src#/etc/iris-ca/}"
    safe_name="iris-dropin-${rel//\//_}"
    # update-ca-certificates only picks up files ending in .crt.
    [[ "${safe_name}" == *.crt ]] || safe_name="${safe_name}.crt"
    dst="/usr/local/share/ca-certificates/${safe_name}"
    if [[ ! -f "${dst}" ]] || ! cmp -s "${ca_src}" "${dst}"; then
      printf "Installing drop-in CA: %s\n" "${rel}"
      cp "${ca_src}" "${dst}"
      _iris_ca_installed_any=1
    fi
  done < <(find /etc/iris-ca -maxdepth 4 -type f \( -name '*.crt' -o -name '*.pem' \) -print0 2>/dev/null)
fi

if [[ "${_iris_ca_installed_any}" -eq 1 ]]; then
  update-ca-certificates --fresh >/dev/null 2>&1 || \
    printf "WARN: update-ca-certificates failed (CAs not registered)\n"
fi

# ----------------------------------------------------------------------
# Point Python's HTTPS libraries at the OS trust store.
#
# `requests`, `urllib3`, and any library that goes through them (the
# `oic` OIDC client, webhook integrations, ...) default to certifi's
# bundle (/opt/venv/.../certifi/cacert.pem) — a hard-coded copy of
# Mozilla's public roots that does NOT include any CA we just
# installed. Setting REQUESTS_CA_BUNDLE / SSL_CERT_FILE to Debian's
# consolidated bundle (which update-ca-certificates rebuilt above)
# makes every Python HTTPS call trust the OS store, so the drop-in
# CAs are effective.
#
# Only set when the operator hasn't pinned these env vars themselves,
# so existing deployments that point at a bespoke bundle continue to
# work unchanged.
if [[ -z "${REQUESTS_CA_BUNDLE:-}" ]] && [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
  export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
fi
if [[ -z "${SSL_CERT_FILE:-}" ]] && [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
fi

printf "Running ${target} ...\n"

trap 'pkill "^(celery|gunicorn)"; exit 0' TERM INT

if [[ "${target}" == iris-worker ]] ; then
    if [[ -z $NUMBER_OF_CHILD ]]; then
        celery -A app.celery worker -E -B -l $LOG_LEVEL &
    else
        celery -A app.celery worker -c $NUMBER_OF_CHILD -E -B -l $LOG_LEVEL &
    fi
else
    gunicorn app:app --bind 0.0.0.0:8000 --timeout 180 --worker-connections 1000 --threads 100 -w 1 --log-level=info &
fi

while :; do tail -f /dev/null & wait $!; done
