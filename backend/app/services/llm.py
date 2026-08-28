from openai import AsyncOpenAI
from .retrieval import Candidate
from ..config import get_settings

class LLMService:
    def __init__(self):
        self.settings=get_settings();self.client=AsyncOpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None
    async def embed(self,texts:list[str])->list[list[float]]:
        if not self.client: raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        result=await self.client.embeddings.create(model=self.settings.embedding_model,input=texts,dimensions=self.settings.embedding_dimensions)
        return [x.embedding for x in result.data]
    async def rewrite(self,query:str)->str:
        if not self.client:return query
        response=await self.client.responses.create(model=self.settings.chat_model,input=f"将问题改写为适合企业知识库检索的独立中文查询，只输出查询：{query}")
        return response.output_text.strip()
    async def rerank(self,query:str,candidates:list[Candidate],top_k:int)->list[Candidate]:
        # Deterministic lexical rerank fallback. Replace with a cross-encoder service in high-throughput deployments.
        q=set(query.lower());
        for c in candidates:c.rerank_score=.7*c.score+.3*len(q&set(c.text.lower()))/max(len(q),1)
        return sorted(candidates,key=lambda x:x.rerank_score,reverse=True)[:top_k]
    async def answer(self,query:str,contexts:list[Candidate],memories:list[str])->tuple[str,dict]:
        if not self.client:return "模型服务尚未配置。检索已完成，请设置 OPENAI_API_KEY。",{"input_tokens":0,"output_tokens":0}
        context="\n\n".join(f"[{i+1}] {c.breadcrumb}\n{c.parent_text or c.text}" for i,c in enumerate(contexts))
        memory="\n".join(memories)
        response=await self.client.responses.create(model=self.settings.chat_model,input=f"你是企业知识助手。只依据上下文回答，缺失时明确说不知道。\n已确认反馈：{memory}\n上下文：{context}\n问题：{query}")
        usage=getattr(response,"usage",None)
        return response.output_text,{"input_tokens":getattr(usage,"input_tokens",0),"output_tokens":getattr(usage,"output_tokens",0)}

