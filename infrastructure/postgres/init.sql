-- =============================================================================
-- LitReviewer — PostgreSQL Initialisation
-- Runs once on first container startup via docker-entrypoint-initdb.d/.
-- The database and user are created automatically by the POSTGRES_DB /
-- POSTGRES_USER / POSTGRES_PASSWORD environment variables on the image.
-- This script handles any extensions and privileges needed on top of that.
-- =============================================================================

-- Enable pgcrypto so gen_random_uuid() is available in all schemas.
-- Used by every table that uses UUID primary keys.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure the application user owns the public schema so Alembic can create
-- and alter tables without needing superuser privileges.
ALTER SCHEMA public OWNER TO research_user;

GRANT ALL PRIVILEGES ON SCHEMA public TO research_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO research_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO research_user;

-- Set default privileges so future tables are automatically accessible.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO research_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO research_user;
