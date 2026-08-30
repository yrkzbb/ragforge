import asyncio
from dataclasses import dataclass

from opentelemetry.trace import Status, StatusCode
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings
from .llm import LLMService
from .memory import FeedbackMemoryService
from .search import SearchService


class AgentExecutionError(RuntimeError):
    pass


@dataclass
class AgentResult:
    answer: str
    contexts: list
    memory_items: list
    usage: dict
    iterations: int
    handoffs: list
    loop_steps: list
    status: str


class ReActAgent:
    def __init__(self, db, tracer, llm=None):
        self.db = db
        self.tracer = tracer
        self.llm = llm or LLMService()
        self.settings = get_settings()

    def _handoff(self, source: str, destination: str, reason: str, iteration: int):
        with self.tracer.start_as_current_span("agent.handoff") as span:
            span.set_attribute("agent.from", source)
            span.set_attribute("agent.to", destination)
            span.set_attribute("agent.handoff.reason", reason)
            span.set_attribute("agent.iteration", iteration)

    async def _node(self, name, operation):
        """Run one node with a deadline and bounded exponential-backoff retries."""
        attempts = self.settings.agent_retry_attempts
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(
                multiplier=self.settings.agent_retry_min_seconds,
                max=self.settings.agent_retry_max_seconds,
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                with self.tracer.start_as_current_span(f"agent.node.{name}") as span:
                    span.set_attribute("agent.node", name)
                    span.set_attribute("agent.attempt", attempt.retry_state.attempt_number)
                    try:
                        async with asyncio.timeout(self.settings.agent_node_timeout_seconds):
                            return await operation()
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        raise

    async def run(self, body):
        observations, contexts, memory_items = [], [], []
        usage = {"input_tokens": 0, "output_tokens": 0}
        handoffs = []
        loop_steps = [{"iteration": 0, "phase": "perceive", "title": "感知任务与上下文", "detail": body.message, "status": "completed"}]

        for iteration in range(1, self.settings.agent_max_iterations + 1):
            decision, step_usage = await self._node(
                "reason", lambda: self.llm.react_step(body.message, observations)
            )
            loop_steps.append({"iteration": iteration, "phase": "think", "title": "思考并选择下一步", "detail": "已有证据足够，准备完成任务" if decision["action"] == "final" else f"选择工具：{decision['action']}", "status": "completed"})
            for key in usage:
                usage[key] += step_usage.get(key, 0)

            if decision["action"] == "final":
                loop_steps.append({"iteration": iteration, "phase": "complete", "title": "任务完成", "detail": "已生成最终结果并退出循环", "status": "completed"})
                return AgentResult(decision["answer"], contexts, memory_items, usage, iteration, handoffs, loop_steps, "completed")

            if decision["action"] != "knowledge_base_search":
                raise AgentExecutionError(f"unsupported action: {decision['action']}")

            self._handoff("orchestrator", "retrieval-agent", "knowledge_required", iteration)
            handoffs.append({"from": "orchestrator", "to": "retrieval-agent"})
            with self.tracer.start_as_current_span("tool.call") as tool_span:
                tool_span.set_attribute("tool.name", "knowledge_base_search")
                tool_span.set_attribute("tool.type", "retrieval")
                _, contexts = await self._node(
                    "knowledge_base_search",
                    lambda: SearchService(self.db).search(
                        body.knowledge_base_id, decision["query"], 8, 30
                    ),
                )
                tool_span.set_attribute("tool.result.count", len(contexts))
            loop_steps.append({"iteration": iteration, "phase": "act", "title": "执行知识库检索", "detail": decision["query"], "status": "completed"})

            memory_service = FeedbackMemoryService(self.db)
            memory_items = await self._node(
                "memory", lambda: memory_service.select_for_chat(
                    body.user_id, body.knowledge_base_id, body.message
                )
            )
            await self._node("memory_record", lambda: memory_service.record_injections(memory_items))
            observations.append({
                "tool": "knowledge_base_search",
                "query": decision["query"],
                "results": [
                    {"breadcrumb": item.breadcrumb, "content": item.parent_text or item.text,
                     "score": item.rerank_score}
                    for item in contexts
                ],
                "confirmed_feedback": [
                    {"scope": item.scope, "correction": item.correction, "reason": item.reason}
                    for item in memory_items
                ],
            })
            loop_steps.append({"iteration": iteration, "phase": "observe", "title": "观察工具结果", "detail": f"获得 {len(contexts)} 个候选分块与 {len(memory_items)} 条已确认记忆", "status": "completed"})
            self._handoff("retrieval-agent", "orchestrator", "observation_ready", iteration)
            handoffs.append({"from": "retrieval-agent", "to": "orchestrator"})

        raise AgentExecutionError(
            f"agent exceeded maximum iterations ({self.settings.agent_max_iterations})"
        )
