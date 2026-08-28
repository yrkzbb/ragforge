ALTER TABLE feedback_memories ADD COLUMN IF NOT EXISTS source_trace_id VARCHAR(64);
ALTER TABLE feedback_memories ADD COLUMN IF NOT EXISTS use_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE feedback_memories ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_feedback_source_trace_id ON feedback_memories(source_trace_id);
