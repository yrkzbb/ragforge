from openai import AsyncOpenAI
from .retrieval import Candidate
from ..config import get_settings
from .reranker import CrossEncoderReranker

class LLMService:
    def __init__(self):
        self.settings=get_settings();self.client=AsyncOpenAI(api_key=self.settings.openai_api_key,base_url=self.settings.openai_base_url) if self.settings.openai_api_key else None
    async def embed(self,texts:list[str])->list[list[float]]:
        if not self.client: raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        result=await self.client.embeddings.create(model=self.settings.embedding_model,input=texts,dimensions=self.settings.embedding_dimensions)
        return [x.embedding for x in result.data]
    async def rewrite(self,query:str)->str:
        if not self.client:return query
        response=await self.client.chat.completions.create(model=self.settings.chat_model,messages=[{"role":"system","content":"将用户问题改写为适合企业知识库检索的独立中文查询，只输出查询。"},{"role":"user","content":query}],temperature=0)
        return (response.choices[0].message.content or query).strip()
    async def rerank(self,query:str,candidates:list[Candidate],top_k:int)->list[Candidate]:
        return await CrossEncoderReranker().rank(query,candidates,top_k)
    async def answer(self,query:str,contexts:list[Candidate],memories:list[str])->tuple[str,dict]:
        if not self.client:return "模型服务尚未配置。检索已完成，请设置 OPENAI_API_KEY。",{"input_tokens":0,"output_tokens":0}
        context="\n\n".join(f"[{i+1}] {c.breadcrumb}\n{c.parent_text or c.text}" for i,c in enumerate(contexts))
        memory="\n".join(memories)
        response=await self.client.chat.completions.create(model=self.settings.chat_model,messages=[{"role":"system","content":"你是企业知识助手。只依据给定上下文回答；上下文缺失时明确说不知道。已确认反馈仅在适用时使用。"},{"role":"user","content":f"已确认反馈：\n{memory}\n\n上下文：\n{context}\n\n问题：{query}"}],temperature=0)
        usage=getattr(response,"usage",None)
        return response.choices[0].message.content or "",{"input_tokens":getattr(usage,"prompt_tokens",0),"output_tokens":getattr(usage,"completion_tokens",0)}
