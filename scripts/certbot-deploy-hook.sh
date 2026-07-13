#!/usr/bin/env bash
#
# Certbot deploy-hook for IRIS.
#
# Wire this into certbot so renewed certificates land in the bind
# volume IRIS's nginx already reads from (./certificates/web_certificates/).
# The nginx entrypoint watches that directory for cert mtime changes
# and issues `nginx -s reload` on its own — no container restart, no
# manual copy step.
#
# Install (host, one-time):
#   sudo cp iris-web/scripts/certbot-deploy-hook.sh /etc/letsencrypt/renewal-hooks/deploy/iris.sh
#   sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/iris.sh
#   # Point IRIS_WEB_CERT_DIR at your absolute path to certificates/web_certificates/
#   sudo sed -i 's|__IRIS_WEB_CERT_DIR__|/opt/iris/iris-web/certificates/web_certificates|' \
#       /etc/letsencrypt/renewal-hooks/deploy/iris.sh
#
# Certbot will invoke this after every successful renewal.  Set
# RENEWED_LINEAGE (certbot does this automatically) or pass it in
# manually to test.

set -eu

# Absolute path to iris-web/certificates/web_certificates/ on the host.
# Override on the command line or edit this default.
IRIS_WEB_CERT_DIR="${IRIS_WEB_CERT_DIR:-__IRIS_WEB_CERT_DIR__}"

if [ -z "${RENEWED_LINEAGE:-}" ]; then
    echo "certbot-deploy-hook: RENEWED_LINEAGE unset — invoke via certbot --deploy-hook" >&2
    exit 1
fi

if [ ! -d "${IRIS_WEB_CERT_DIR}" ]; then
    echo "certbot-deploy-hook: ${IRIS_WEB_CERT_DIR} does not exist" >&2
    exit 1
fi

# Install with permissions that let the nginx container (uid mapped to
# www-data) read the material while denying world access to the key.
install -m 0644 "${RENEWED_LINEAGE}/fullchain.pem" "${IRIS_WEB_CERT_DIR}/fullchain.pem"
install -m 0640 "${RENEWED_LINEAGE}/privkey.pem"   "${IRIS_WEB_CERT_DIR}/privkey.pem"

echo "certbot-deploy-hook: refreshed certs in ${IRIS_WEB_CERT_DIR}"
# The nginx container's watcher will notice the mtime change and
# reload on its next tick (default 60s).
