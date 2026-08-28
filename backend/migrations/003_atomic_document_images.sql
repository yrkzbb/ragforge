ALTER TABLE documents ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
CREATE INDEX IF NOT EXISTS ix_documents_active ON documents(knowledge_base_id, active);
-- PostgreSQL enforces a single compiler per knowledge base, independently of Celery replicas.
CREATE UNIQUE INDEX IF NOT EXISTS ux_build_jobs_one_active_per_kb
  ON build_jobs(knowledge_base_id) WHERE state IN ('leased', 'running');
