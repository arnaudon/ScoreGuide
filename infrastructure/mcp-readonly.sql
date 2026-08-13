-- Idempotent setup/rotation for the SELECT-only `mcp_readonly` role, for
-- Postgres volumes that already existed before postgres-init ran (the
-- docker-entrypoint-initdb.d script only runs on an empty data volume).
--
-- Requires the `mcp_password` psql variable; run e.g. from the VPS:
--
--   docker exec -i -e MCP_READONLY_PASSWORD="$MCP_READONLY_PASSWORD" postgres_db \
--     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--            -v mcp_password="${MCP_READONLY_PASSWORD:-readonly}"' \
--     < infrastructure/mcp-readonly.sql
--
-- Safe to run multiple times — the deploy workflow runs it on every deploy,
-- which also rotates the password to the current secret.

SELECT 'CREATE ROLE mcp_readonly LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mcp_readonly')
\gexec

ALTER ROLE mcp_readonly LOGIN PASSWORD :'mcp_password';

GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_readonly;
