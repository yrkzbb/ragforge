from types import SimpleNamespace

import pytest
from opentelemetry import trace

from app.config import get_settings
from app.services import agent as agent_module
from app.services.agent import AgentExecutionError, ReActAgent


class FakeLLM:
    def __init__(self, decisions):
        self.decisions = iter(decisions)

    async def react_step(self, query, observations):
        return next(self.decisions), {"input_tokens": 2, "output_tokens": 1}


class FakeSearch:
    def __init__(self, db):
        pass

    async def search(self, *args):
        item = SimpleNamespace(
            id="chunk-1", breadcrumb="制度 / 请假", parent_text="年假为十天", text="",
            rerank_score=0.9,
        )
        return args[1], [item]


class FakeMemory:
    def __init__(self, db):
        pass

    async def select_for_chat(self, *args):
        return []

    async def record_injections(self, items):
        return None


@pytest.fixture(autouse=True)
def fast_agent_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_retry_min_seconds", 0)
    monkeypatch.setattr(settings, "agent_retry_max_seconds", 0)
    monkeypatch.setattr(agent_module, "SearchService", FakeSearch)
    monkeypatch.setattr(agent_module, "FeedbackMemoryService", FakeMemory)


@pytest.mark.asyncio
async def test_react_agent_searches_then_answers():
    llm = FakeLLM([
        {"action": "knowledge_base_search", "query": "年假天数"},
        {"action": "final", "answer": "年假为十天。"},
    ])
    body = SimpleNamespace(message="年假几天？", user_id="u1", knowledge_base_id="kb1")
    result = await ReActAgent(None, trace.get_tracer(__name__), llm=llm).run(body)
    assert result.answer == "年假为十天。"
    assert result.iterations == 2
    assert result.contexts[0].id == "chunk-1"
    assert result.usage == {"input_tokens": 4, "output_tokens": 2}
    assert result.status == "completed"
    assert [step["phase"] for step in result.loop_steps] == ["perceive", "think", "act", "observe", "think", "complete"]


@pytest.mark.asyncio
async def test_react_agent_stops_at_max_iterations(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_max_iterations", 2)
    llm = FakeLLM([
        {"action": "knowledge_base_search", "query": "q1"},
        {"action": "knowledge_base_search", "query": "q2"},
    ])
    body = SimpleNamespace(message="question", user_id="u1", knowledge_base_id="kb1")
    with pytest.raises(AgentExecutionError, match="maximum iterations"):
        await ReActAgent(None, trace.get_tracer(__name__), llm=llm).run(body)


@pytest.mark.asyncio
async def test_node_retries_transient_failure():
    runner = ReActAgent(None, trace.get_tracer(__name__), llm=FakeLLM([]))
    attempts = 0

    async def flaky():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    assert await runner._node("flaky", flaky) == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_node_timeout_is_bounded(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_node_timeout_seconds", 0.01)
    monkeypatch.setattr(settings, "agent_retry_attempts", 1)
    runner = ReActAgent(None, trace.get_tracer(__name__), llm=FakeLLM([]))

    async def slow():
        import asyncio
        await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        await runner._node("slow", slow)
