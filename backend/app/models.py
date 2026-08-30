import enum
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from .config import get_settings

class Base(DeclarativeBase): pass
class BuildState(str, enum.Enum): queued="queued"; leased="leased"; running="running"; succeeded="succeeded"; failed="failed"
class FeedbackState(str, enum.Enum): pending="pending"; accepted="accepted"; rejected="rejected"

class Conversation(Base):
    __tablename__="conversations"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    client_id:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    user_id:Mapped[str]=mapped_column(String(200),index=True)
    knowledge_base_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("knowledge_bases.id",ondelete="SET NULL"),nullable=True,index=True)
    title:Mapped[str]=mapped_column(String(300),default="新任务")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),index=True)

class ConversationMessage(Base):
    __tablename__="conversation_messages"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    conversation_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("conversations.id",ondelete="CASCADE"),index=True)
    role:Mapped[str]=mapped_column(String(20))
    content:Mapped[str]=mapped_column(Text)
    payload:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)

class KnowledgeBase(Base):
    __tablename__="knowledge_bases"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    name:Mapped[str]=mapped_column(String(200),unique=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class Document(Base):
    __tablename__="documents"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    knowledge_base_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("knowledge_bases.id",ondelete="CASCADE"),index=True)
    source_uri:Mapped[str]=mapped_column(String(1000))
    title:Mapped[str]=mapped_column(String(500))
    original_text:Mapped[str|None]=mapped_column(Text,nullable=True)
    content_hash:Mapped[str]=mapped_column(String(64),index=True)
    version:Mapped[int]=mapped_column(Integer,default=1)
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    __table_args__=(UniqueConstraint("knowledge_base_id","source_uri","version"),)

class Chunk(Base):
    __tablename__="chunks"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    document_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("documents.id",ondelete="CASCADE"),index=True)
    parent_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("chunks.id",ondelete="CASCADE"),nullable=True,index=True)
    ordinal:Mapped[int]=mapped_column(Integer)
    level:Mapped[str]=mapped_column(String(20))
    breadcrumb:Mapped[str]=mapped_column(String(1000),default="")
    text:Mapped[str]=mapped_column(Text)
    token_count:Mapped[int]=mapped_column(Integer,default=0)
    embedding:Mapped[list[float]|None]=mapped_column(Vector(get_settings().embedding_dimensions),nullable=True)
    parent=relationship("Chunk",remote_side=[id])
    __table_args__=(Index("ix_chunks_embedding_hnsw","embedding",postgresql_using="hnsw",postgresql_ops={"embedding":"vector_cosine_ops"}),)

class ChangeEvent(Base):
    __tablename__="change_events"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    knowledge_base_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("knowledge_bases.id",ondelete="CASCADE"),index=True)
    source_uri:Mapped[str]=mapped_column(String(1000))
    operation:Mapped[str]=mapped_column(String(20))
    payload:Mapped[dict]=mapped_column(JSON,default=dict)
    consumed:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)

class BuildJob(Base):
    __tablename__="build_jobs"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    knowledge_base_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("knowledge_bases.id",ondelete="CASCADE"),index=True)
    image_version:Mapped[int]=mapped_column(Integer)
    state:Mapped[BuildState]=mapped_column(Enum(BuildState),default=BuildState.queued,index=True)
    lease_owner:Mapped[str|None]=mapped_column(String(200),nullable=True)
    lease_expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    attempts:Mapped[int]=mapped_column(Integer,default=0)
    error:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
    __table_args__=(UniqueConstraint("knowledge_base_id","image_version"),)

class FeedbackMemory(Base):
    __tablename__="feedback_memories"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[str]=mapped_column(String(200),index=True)
    knowledge_base_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey("knowledge_bases.id",ondelete="CASCADE"),nullable=True,index=True)
    correction:Mapped[str]=mapped_column(Text)
    reason:Mapped[str]=mapped_column(Text)
    scope:Mapped[str]=mapped_column(String(500),index=True)
    confidence:Mapped[float]=mapped_column(Float,default=0.8)
    state:Mapped[FeedbackState]=mapped_column(Enum(FeedbackState),default=FeedbackState.pending,index=True)
    embedding:Mapped[list[float]|None]=mapped_column(Vector(get_settings().embedding_dimensions),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    source_trace_id:Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    use_count:Mapped[int]=mapped_column(Integer,default=0)
    last_used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class EvalRun(Base):
    __tablename__="eval_runs"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    dataset_name:Mapped[str]=mapped_column(String(300))
    config:Mapped[dict]=mapped_column(JSON,default=dict)
    metrics:Mapped[dict]=mapped_column(JSON,default=dict)
    passed:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
