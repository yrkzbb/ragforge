CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN CREATE TYPE buildstate AS ENUM ('queued','leased','running','succeeded','failed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE feedbackstate AS ENUM ('pending','accepted','rejected'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS knowledge_bases(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),name varchar(200) UNIQUE NOT NULL,created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS documents(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),knowledge_base_id uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,source_uri varchar(1000) NOT NULL,title varchar(500) NOT NULL,content_hash varchar(64) NOT NULL,version integer NOT NULL DEFAULT 1,metadata_json jsonb NOT NULL DEFAULT '{}',created_at timestamptz DEFAULT now(),UNIQUE(knowledge_base_id,source_uri,version));
CREATE INDEX IF NOT EXISTS ix_documents_kb ON documents(knowledge_base_id);
CREATE TABLE IF NOT EXISTS chunks(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,parent_id uuid REFERENCES chunks(id) ON DELETE CASCADE,ordinal integer NOT NULL,level varchar(20) NOT NULL,breadcrumb varchar(1000) NOT NULL DEFAULT '',text text NOT NULL,token_count integer NOT NULL DEFAULT 0,embedding vector(1536));
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(document_id); CREATE INDEX IF NOT EXISTS ix_chunks_parent ON chunks(parent_id);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS change_events(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),knowledge_base_id uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,source_uri varchar(1000) NOT NULL,operation varchar(20) NOT NULL,payload jsonb NOT NULL DEFAULT '{}',consumed boolean NOT NULL DEFAULT false,created_at timestamptz DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_change_events_pending ON change_events(knowledge_base_id,consumed,created_at);
CREATE TABLE IF NOT EXISTS build_jobs(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),knowledge_base_id uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,image_version integer NOT NULL,state buildstate NOT NULL DEFAULT 'queued',lease_owner varchar(200),lease_expires_at timestamptz,attempts integer NOT NULL DEFAULT 0,error text,created_at timestamptz DEFAULT now(),updated_at timestamptz DEFAULT now(),UNIQUE(knowledge_base_id,image_version));
CREATE INDEX IF NOT EXISTS ix_build_jobs_state ON build_jobs(state);
CREATE TABLE IF NOT EXISTS feedback_memories(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),user_id varchar(200) NOT NULL,correction text NOT NULL,reason text NOT NULL,scope varchar(500) NOT NULL,confidence double precision NOT NULL DEFAULT .8,state feedbackstate NOT NULL DEFAULT 'pending',embedding vector(1536),created_at timestamptz DEFAULT now(),reviewed_at timestamptz);
CREATE INDEX IF NOT EXISTS ix_feedback_user_state ON feedback_memories(user_id,state);
CREATE TABLE IF NOT EXISTS eval_runs(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),dataset_name varchar(300) NOT NULL,config jsonb NOT NULL DEFAULT '{}',metrics jsonb NOT NULL DEFAULT '{}',passed boolean NOT NULL DEFAULT false,created_at timestamptz DEFAULT now());

