import pytest

from app.services.reranker import CrossEncoderReranker
from app.services.retrieval import Candidate


@pytest.mark.asyncio
async def test_disabled_reranker_has_deterministic_fallback(monkeypatch):
    reranker = CrossEncoderReranker()
    monkeypatch.setattr(reranker.settings, "reranker_enabled", False)
    candidates = [Candidate("1", "密码重置流程", "a", "a"), Candidate("2", "采购审批", "b", "b")]
    result = await reranker.rank("如何重置密码", candidates, 1)
    assert result[0].id == "1"
