#!/bin/bash
set -e

POSTGRES="psql --username ${POSTGRES_USER}"

echo "Creating database role: ${DB_USER}"

$POSTGRES <<-EOSQL
CREATE USER ${DB_USER} WITH CREATEDB SUPERUSER PASSWORD '${DB_PASS}';
EOSQL