-- Runs once on first boot against an empty volume.
-- Reset by: `docker compose down -v`.

CREATE EXTENSION IF NOT EXISTS vector;

-- Table DDL lives in Step 3 (SQLAlchemy create_all via `jmi init-db`)
-- and will migrate to Alembic in Week 2.
