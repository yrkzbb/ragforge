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

    def _protect_base_top(self, candidates: list[Candidate], ranked: list[Candidate]) -> list[Candidate]:
        protected = candidates[:self.settings.reranker_protect_top_n]
        protected_ids = {item.id for item in protected}
        return protected + [item for item in ranked if item.id not in protected_ids]

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
                ranked = self._fallback(query, candidates)
                return self._protect_base_top(candidates, ranked)[:top_k]
            try:
                model = await asyncio.to_thread(_load_model, self.settings.reranker_model)
                inputs = [f"{item.breadcrumb}\n{item.text}\n{item.parent_text[:1000]}" for item in candidates]
                scores = await asyncio.to_thread(
                    model.rerank, query, inputs,
                    batch_size=self.settings.reranker_batch_size,
                )
                model_order = sorted(range(len(candidates)), key=lambda index: float(scores[index]), reverse=True)
                model_rank = {candidate_index: rank for rank, candidate_index in enumerate(model_order, 1)}
                weight = self.settings.reranker_model_weight
                for base_rank, candidate in enumerate(candidates, 1):
                    candidate.rerank_score = weight / (60 + model_rank[base_rank - 1]) + (1 - weight) / (60 + base_rank)
                span.set_attribute("reranker.mode", "cross_encoder")
                span.set_attribute("reranker.model_weight", weight)
                ranked = sorted(candidates, key=lambda item: item.rerank_score, reverse=True)
                return self._protect_base_top(candidates, ranked)[:top_k]
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("reranker.mode", "fallback_error")
                span.set_attribute("reranker.error", type(exc).__name__)
                ranked = self._fallback(query, candidates)
                return self._protect_base_top(candidates, ranked)[:top_k]
