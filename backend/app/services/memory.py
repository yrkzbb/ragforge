from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FeedbackMemory, FeedbackState
from .llm import LLMService


def _lexical_relevance(query: str, item: FeedbackMemory) -> float:
    query_chars = set(query.lower())
    memory_chars = set(f"{item.scope}{item.reason}{item.correction}".lower())
    return len(query_chars & memory_chars) / max(len(query_chars), 1)


class FeedbackMemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def select_for_chat(self, user_id: str, knowledge_base_id, query: str, limit: int = 5):
        condition = [
            FeedbackMemory.user_id == user_id,
            FeedbackMemory.state == FeedbackState.accepted,
            or_(FeedbackMemory.knowledge_base_id == knowledge_base_id, FeedbackMemory.knowledge_base_id.is_(None)),
        ]
        try:
            vector = (await LLMService().embed([query]))[0]
            distance = FeedbackMemory.embedding.cosine_distance(vector)
            rows = (await self.db.scalars(
                select(FeedbackMemory).where(*condition, FeedbackMemory.embedding.is_not(None), distance <= 0.45)
                .order_by(distance, FeedbackMemory.confidence.desc()).limit(limit)
            )).all()
            if rows:
                return rows
        except RuntimeError:
            pass
        candidates = (await self.db.scalars(
            select(FeedbackMemory).where(*condition).order_by(FeedbackMemory.confidence.desc()).limit(50)
        )).all()
        ranked = sorted(candidates, key=lambda item: _lexical_relevance(query, item), reverse=True)
        return [item for item in ranked if _lexical_relevance(query, item) >= 0.12][:limit]
