from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://ragforge:ragforge@postgres:5432/ragforge"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_enabled: bool = True
    reranker_batch_size: int = 16
    reranker_model_weight: float = Field(0.35, ge=0.0, le=1.0)
    reranker_candidate_k: int = Field(15, ge=1, le=100)
    reranker_protect_top_n: int = Field(1, ge=0, le=10)
    otlp_endpoint: str = "http://otel-collector:4317"
    jaeger_query_url: str = "http://jaeger:16686"
    chat_input_cost_per_million: float = 0.0
    chat_output_cost_per_million: float = 0.0
    cors_origins: str = "http://localhost:3000"
    compile_debounce_seconds: int = 3
    worker_lease_seconds: int = 300
    agent_max_iterations: int = Field(4, ge=1, le=12)
    agent_node_timeout_seconds: float = Field(20.0, gt=0, le=120)
    agent_retry_attempts: int = Field(3, ge=1, le=6)
    agent_retry_min_seconds: float = Field(0.25, ge=0, le=10)
    agent_retry_max_seconds: float = Field(2.0, ge=0, le=30)

@lru_cache
def get_settings() -> Settings:
    return Settings()
