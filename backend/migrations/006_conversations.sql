CREATE TABLE IF NOT EXISTS conversations(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id VARCHAR(100) UNIQUE NOT NULL,
  user_id VARCHAR(200) NOT NULL,
  knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE SET NULL,
  title VARCHAR(300) NOT NULL DEFAULT '新任务',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conversations_user_updated ON conversations(user_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS conversation_messages(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL,
  content TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conversation_messages_order ON conversation_messages(conversation_id,created_at,id);
