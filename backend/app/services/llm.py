import json
import re

from openai import AsyncOpenAI
from .retrieval import Candidate
from ..config import get_settings
from .reranker import CrossEncoderReranker

class LLMService:
    def __init__(self):
        self.settings=get_settings()
        self.client=AsyncOpenAI(api_key=self.settings.openai_api_key,base_url=self.settings.openai_base_url) if self.settings.openai_api_key else None
    async def embed(self,texts:list[str])->list[list[float]]:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        result=await self.client.embeddings.create(model=self.settings.embedding_model,input=texts,dimensions=self.settings.embedding_dimensions)
        return [x.embedding for x in result.data]
    async def rewrite(self,query:str)->str:
        normalized=self.normalize_query(query)
        if not self.client:
            return normalized
        response=await self.client.chat.completions.create(model=self.settings.chat_model,messages=[{"role":"system","content":"将用户问题改写为适合企业知识库检索的独立中文查询。展开企业常用简称和同义词，必须保留编号、日期、版本等精确标识，只输出查询。"},{"role":"user","content":normalized}],temperature=0)
        return (response.choices[0].message.content or normalized).strip()

    @staticmethod
    def normalize_query(query:str)->str:
        aliases={
            "HR":"人力资源", "人事管理":"人力资源", "数据防护":"信息安全",
            "费用管控":"财务管理", "客诉支持":"客户服务", "技术研发":"研发工程",
            "供应商采买":"采购管理", "增长运营":"市场运营", "法律风控":"法务合规",
            "综合事务":"行政管理", "灾备恢复":"业务连续性",
        }
        normalized=query
        for alias,canonical in aliases.items():
            normalized=re.sub(re.escape(alias),canonical,normalized,flags=re.IGNORECASE)
        numerals={"一":"01","二":"02","三":"03","四":"04","五":"05","六":"06","七":"07","八":"08","九":"09","十":"10"}
        return re.sub(r"([一二三四五六七八九十])号",lambda match:f"{numerals[match.group(1)]}号",normalized)
    async def rerank(self,query:str,candidates:list[Candidate],top_k:int)->list[Candidate]:
        return await CrossEncoderReranker().rank(query,candidates,top_k)
    async def answer(self,query:str,contexts:list[Candidate],memories:list[str])->tuple[str,dict]:
        if not self.client:
            return "模型服务尚未配置。检索已完成，请设置 OPENAI_API_KEY。",{"input_tokens":0,"output_tokens":0}
        context="\n\n".join(f"[{i+1}] {c.breadcrumb}\n{c.parent_text or c.text}" for i,c in enumerate(contexts))
        memory="\n".join(memories)
        response=await self.client.chat.completions.create(model=self.settings.chat_model,messages=[{"role":"system","content":"你是企业知识助手。只依据给定上下文回答；上下文缺失时明确说不知道。已确认反馈仅在适用时使用。"},{"role":"user","content":f"已确认反馈：\n{memory}\n\n上下文：\n{context}\n\n问题：{query}"}],temperature=0)
        usage=getattr(response,"usage",None)
        return response.choices[0].message.content or "",{"input_tokens":getattr(usage,"prompt_tokens",0),"output_tokens":getattr(usage,"completion_tokens",0)}

    async def react_step(self, query: str, observations: list[dict]) -> tuple[dict, dict]:
        """Ask the model for the next ReAct action without exposing chain-of-thought."""
        if not self.client:
            if not observations:
                return {"action": "knowledge_base_search", "query": query}, {"input_tokens": 0, "output_tokens": 0}
            return {"action": "final", "answer": "模型服务尚未配置。检索已完成，请设置 OPENAI_API_KEY。"}, {"input_tokens": 0, "output_tokens": 0}
        tools = [{
            "type": "function",
            "function": {
                "name": "knowledge_base_search",
                "description": "在当前企业知识库中检索回答问题所需的事实。回答知识问题前必须调用。",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "独立、完整的检索查询"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }]
        messages = [{"role": "system", "content": (
            "你是企业知识库 ReAct Agent。先分析问题，再选择工具；工具结果是 Observation。"
            "没有 Observation 时必须调用 knowledge_base_search。获得足够证据后直接给出最终答案；"
            "优先依据 Observation 回答。若检索结果为空或相关性不足，可以使用通用知识回答，"
            "但必须明确标注‘以下回答来自模型通用知识，未在当前知识库中找到依据’。"
            "不得伪造知识库来源或引用。不要输出思维过程。"
        )}, {"role": "user", "content": query}]
        for observation in observations:
            messages.append({"role": "assistant", "content": "我将检索知识库。"})
            messages.append({"role": "user", "content": "Observation:\n" + json.dumps(observation, ensure_ascii=False)})
        response = await self.client.chat.completions.create(
            model=self.settings.chat_model, messages=messages, tools=tools,
            tool_choice="required" if not observations else "auto", temperature=0,
        )
        message = response.choices[0].message
        usage = getattr(response, "usage", None)
        token_usage = {"input_tokens": getattr(usage, "prompt_tokens", 0), "output_tokens": getattr(usage, "completion_tokens", 0)}
        if message.tool_calls:
            call = message.tool_calls[0]
            if call.function.name != "knowledge_base_search":
                raise ValueError(f"unsupported agent tool: {call.function.name}")
            arguments = json.loads(call.function.arguments or "{}")
            search_query = str(arguments.get("query", "")).strip()
            if not search_query:
                raise ValueError("knowledge_base_search requires a non-empty query")
            return {"action": "knowledge_base_search", "query": search_query}, token_usage
        answer = (message.content or "").strip()
        if not answer:
            raise ValueError("agent returned neither a tool call nor an answer")
        return {"action": "final", "answer": answer}, token_usage
