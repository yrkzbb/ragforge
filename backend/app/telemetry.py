from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from .config import get_settings

def configure_telemetry():
    settings=get_settings()
    provider=TracerProvider(resource=Resource.create({"service.name":"ragforge-api","deployment.environment":settings.environment}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint,insecure=True)))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("ragforge")

