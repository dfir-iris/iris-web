#!/usr/bin/env bash

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

set -e

CERTS_DIR="/www/certs"

# Autodetect certbot's standard filenames when the operator hasn't
# pinned CERT_FILENAME / KEY_FILENAME explicitly. Keeping the explicit
# env vars authoritative preserves 100% backward compatibility for
# deployments that already ship custom filenames via .env.
if [ -z "${CERT_FILENAME:-}" ] && [ -f "${CERTS_DIR}/fullchain.pem" ]; then
    export CERT_FILENAME="fullchain.pem"
    echo "[iris-nginx] CERT_FILENAME autodetected: fullchain.pem"
fi
if [ -z "${KEY_FILENAME:-}" ] && [ -f "${CERTS_DIR}/privkey.pem" ]; then
    export KEY_FILENAME="privkey.pem"
    echo "[iris-nginx] KEY_FILENAME autodetected: privkey.pem"
fi

# Strip scheme from SERVER_NAME so operators can drop a full URL in
# .env (e.g. SERVER_NAME=https://iris.lab) without breaking nginx's
# server_name directive. Historical .env files with a bare hostname
# pass through unchanged.
if [ -n "${SERVER_NAME:-}" ]; then
    SERVER_NAME="${SERVER_NAME#http://}"
    SERVER_NAME="${SERVER_NAME#https://}"
    SERVER_NAME="${SERVER_NAME%%/*}"
    export SERVER_NAME
fi

# envsubst will make a substitution on every $variable in a file, since the nginx file contains nginx variable like $host, we have to limit the substitution to this set
# otherwise, each nginx variable will be replaced by an empty string
envsubst '${INTERFACE_HTTPS_PORT} ${IRIS_UPSTREAM_SERVER} ${IRIS_UPSTREAM_PORT} ${SERVER_NAME} ${KEY_FILENAME} ${CERT_FILENAME} ${IRIS_FRONTEND_SERVER} ${IRIS_FRONTEND_PORT}' < /etc/nginx/nginx.conf > /tmp/nginx.conf
cp /tmp/nginx.conf /etc/nginx/nginx.conf
rm /tmp/nginx.conf

# Background cert-reload watcher. When certbot (or any external
# renewal) rewrites the cert file on disk, `nginx -s reload` picks up
# the new material without a container restart. Poll interval is
# controlled by IRIS_CERT_RELOAD_INTERVAL (seconds); set to 0 to
# disable — deployments that manage nginx reloads externally are
# unaffected.
reload_interval="${IRIS_CERT_RELOAD_INTERVAL:-60}"
if [ "${reload_interval}" -gt 0 ] 2>/dev/null && [ -n "${CERT_FILENAME:-}" ]; then
    cert_path="${CERTS_DIR}/${CERT_FILENAME}"
    (
        # Give nginx master a moment to bind before the first stat so
        # we don't race the exec below.
        sleep "${reload_interval}"
        last_mtime=""
        if [ -f "${cert_path}" ]; then
            last_mtime=$(stat -c %Y "${cert_path}" 2>/dev/null || echo "")
        fi
        while true; do
            sleep "${reload_interval}"
            if [ ! -f "${cert_path}" ]; then
                continue
            fi
            current_mtime=$(stat -c %Y "${cert_path}" 2>/dev/null || echo "")
            if [ -n "${current_mtime}" ] && [ "${current_mtime}" != "${last_mtime}" ]; then
                if [ -n "${last_mtime}" ]; then
                    echo "[iris-nginx] cert mtime changed, reloading nginx"
                    nginx -s reload || echo "[iris-nginx] nginx -s reload failed"
                fi
                last_mtime="${current_mtime}"
            fi
        done
    ) &
fi

exec nginx -g "daemon off;"
