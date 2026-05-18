-- Forensa postgres init script
-- CP9.61 - runs once on first volume bootstrap.
-- Alembic migrations create the actual schema; this file is reserved
-- for extensions and roles that must exist BEFORE migrations run.

-- Required by alembic migration 20260513_0930_initial_schema (uuid_generate_v4)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pgcrypto for gen_random_uuid (newer pattern, used by some later migrations)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Reserved for Phase 10 multi-tenant RLS roles (CP10.3):
-- CREATE ROLE forensa_app WITH LOGIN PASSWORD '...';
-- GRANT CONNECT ON DATABASE forensa TO forensa_app;
