from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from .config import get_settings
from prometheus_client import Counter, Histogram

AGENT_REQUESTS = Counter("ragforge_agent_requests_total", "Agent requests", ["operation", "status"])
AGENT_LATENCY = Histogram("ragforge_agent_duration_seconds", "Agent operation latency", ["operation"])
TOKEN_USAGE = Counter("ragforge_llm_tokens_total", "LLM tokens", ["direction", "model"])
LLM_COST = Counter("ragforge_llm_cost_usd_total", "Estimated LLM cost in USD", ["model"])

def configure_telemetry():
    settings=get_settings()
    provider=TracerProvider(resource=Resource.create({"service.name":"ragforge-api","deployment.environment":settings.environment}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint,insecure=True)))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("ragforge")
