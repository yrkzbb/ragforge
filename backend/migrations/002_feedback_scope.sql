ALTER TABLE feedback_memories
  ADD COLUMN IF NOT EXISTS knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_feedback_memories_knowledge_base_id
  ON feedback_memories(knowledge_base_id);
