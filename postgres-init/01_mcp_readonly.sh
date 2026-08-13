#!/bin/sh
# Creates a SELECT-only Postgres role used by the `mcp-postgres` container.
# The MCP SSE server runs with --access-mode=restricted, but this script is
# defense-in-depth: even a prompt-injected INSERT/UPDATE/DELETE can't succeed
# because the role has no write privileges granted.
#
# This file is mounted at /docker-entrypoint-initdb.d/ on the `db` service
# and runs on FIRST initialization only (empty data volume). The password
# comes from MCP_READONLY_PASSWORD (compose default "readonly" for dev) and
# must be alphanumeric — it is interpolated into SQL and a connection URL.
#
# For an existing prod volume, run infrastructure/mcp-readonly.sql instead
# (the deploy workflow does this on every deploy; it's idempotent).
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOF
CREATE USER mcp_readonly WITH PASSWORD '${MCP_READONLY_PASSWORD:-readonly}';

GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_readonly;
EOF
