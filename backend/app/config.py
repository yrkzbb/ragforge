from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://ragforge:ragforge@postgres:5432/ragforge"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    openai_api_key: str = ""
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    otlp_endpoint: str = "http://otel-collector:4317"
    cors_origins: str = "http://localhost:3000"
    compile_debounce_seconds: int = 3
    worker_lease_seconds: int = 300

@lru_cache
def get_settings() -> Settings:
    return Settings()

