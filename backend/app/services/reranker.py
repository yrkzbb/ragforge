from __future__ import annotations

import asyncio
from functools import lru_cache

from opentelemetry import trace

from ..config import get_settings
from .retrieval import Candidate

tracer = trace.get_tracer("ragforge.reranker")


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=model_name)


class CrossEncoderReranker:
    """Lazy, real CrossEncoder reranker with deterministic circuit-breaker fallback."""

    def __init__(self):
        self.settings = get_settings()

    @staticmethod
    def _fallback(query: str, candidates: list[Candidate]) -> list[Candidate]:
        query_chars = set(query.lower())
        for candidate in candidates:
            overlap = len(query_chars & set(candidate.text.lower())) / max(len(query_chars), 1)
            candidate.rerank_score = 0.7 * candidate.score + 0.3 * overlap
        return sorted(candidates, key=lambda item: item.rerank_score, reverse=True)

    async def rank(self, query: str, candidates: list[Candidate], top_k: int) -> list[Candidate]:
        if not candidates:
            return []
        with tracer.start_as_current_span("cross_encoder.predict") as span:
            span.set_attribute("reranker.model", self.settings.reranker_model)
            span.set_attribute("reranker.candidate_count", len(candidates))
            if not self.settings.reranker_enabled:
                span.set_attribute("reranker.mode", "fallback_disabled")
                return self._fallback(query, candidates)[:top_k]
            try:
                model = await asyncio.to_thread(_load_model, self.settings.reranker_model)
                scores = await asyncio.to_thread(
                    model.rerank, query, [item.text for item in candidates],
                    batch_size=self.settings.reranker_batch_size,
                )
                for candidate, score in zip(candidates, scores, strict=True):
                    candidate.rerank_score = float(score)
                span.set_attribute("reranker.mode", "cross_encoder")
                return sorted(candidates, key=lambda item: item.rerank_score, reverse=True)[:top_k]
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("reranker.mode", "fallback_error")
                span.set_attribute("reranker.error", type(exc).__name__)
                return self._fallback(query, candidates)[:top_k]
