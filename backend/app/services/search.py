from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from opentelemetry import trace
from ..models import Chunk, Document
from .llm import LLMService
from .retrieval import Candidate,bm25,rrf

tracer=trace.get_tracer("ragforge.search")
class SearchService:
    def __init__(self,db:AsyncSession):self.db=db;self.llm=LLMService()
    async def search(self,knowledge_base_id,query:str,top_k:int=10,retrieve_k:int=30):
        with tracer.start_as_current_span("query_rewrite") as span:
            rewritten=await self.llm.rewrite(query);span.set_attribute("rag.query.rewritten",rewritten)
        Parent=aliased(Chunk)
        rows=(await self.db.execute(select(Chunk,Parent.text,Document.source_uri).join(Document,Chunk.document_id==Document.id).outerjoin(Parent,Chunk.parent_id==Parent.id).where(Document.knowledge_base_id==knowledge_base_id,Document.active.is_(True),Chunk.level=="child"))).all()
        candidates=[Candidate(str(c.id),c.text,c.breadcrumb,parent or c.text,source_uri) for c,parent,source_uri in rows]
        with tracer.start_as_current_span("bm25_retrieval"): lexical=bm25(rewritten,candidates)[:retrieve_k]
        with tracer.start_as_current_span("dense_retrieval"):
            dense=[]
            try:
                vector=(await self.llm.embed([rewritten]))[0]
                result=(await self.db.execute(select(Chunk,Parent.text,Document.source_uri,(1-Chunk.embedding.cosine_distance(vector)).label("score")).join(Document,Chunk.document_id==Document.id).outerjoin(Parent,Chunk.parent_id==Parent.id).where(Document.knowledge_base_id==knowledge_base_id,Document.active.is_(True),Chunk.level=="child",Chunk.embedding.is_not(None)).order_by(Chunk.embedding.cosine_distance(vector)).limit(retrieve_k))).all()
                dense=[Candidate(str(c.id),c.text,c.breadcrumb,parent or c.text,source_uri,dense_score=float(score)) for c,parent,source_uri,score in result]
            except RuntimeError: dense=lexical
        with tracer.start_as_current_span("rrf_fusion"): fused=rrf([lexical,dense])
        with tracer.start_as_current_span("rerank"): ranked=await self.llm.rerank(query,fused,top_k)
        return rewritten,ranked
