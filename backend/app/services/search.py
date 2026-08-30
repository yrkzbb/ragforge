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
    async def search(self,knowledge_base_id,query:str,top_k:int=10,retrieve_k:int=30,mode:str="bm25_rewrite"):
        if mode not in {"bm25","bm25_rewrite","dense","hybrid_raw","hybrid","full"}:raise ValueError(f"unsupported retrieval mode: {mode}")
        with tracer.start_as_current_span("query_rewrite") as span:
            rewritten=await self.llm.rewrite(query) if mode in {"bm25_rewrite","hybrid","full"} else query
            span.set_attribute("rag.query.rewritten",rewritten);span.set_attribute("rag.ablation.mode",mode)
        Parent=aliased(Chunk)
        rows=(await self.db.execute(select(Chunk,Parent.text,Document.source_uri).join(Document,Chunk.document_id==Document.id).outerjoin(Parent,Chunk.parent_id==Parent.id).where(Document.knowledge_base_id==knowledge_base_id,Document.active.is_(True),Chunk.level=="child"))).all()
        candidates=[Candidate(str(c.id),c.text,c.breadcrumb,parent or c.text,source_uri) for c,parent,source_uri in rows]
        with tracer.start_as_current_span("bm25_retrieval"): lexical=bm25(rewritten,candidates)[:retrieve_k] if mode!="dense" else []
        if mode in {"bm25","bm25_rewrite"}:
            for item in lexical[:top_k]:item.score=item.bm25_score;item.rerank_score=item.bm25_score
            return rewritten,lexical[:top_k]
        with tracer.start_as_current_span("dense_retrieval"):
            dense=[]
            try:
                vector=(await self.llm.embed([rewritten]))[0]
                result=(await self.db.execute(select(Chunk,Parent.text,Document.source_uri,(1-Chunk.embedding.cosine_distance(vector)).label("score")).join(Document,Chunk.document_id==Document.id).outerjoin(Parent,Chunk.parent_id==Parent.id).where(Document.knowledge_base_id==knowledge_base_id,Document.active.is_(True),Chunk.level=="child",Chunk.embedding.is_not(None)).order_by(Chunk.embedding.cosine_distance(vector)).limit(retrieve_k))).all()
                dense=[Candidate(str(c.id),c.text,c.breadcrumb,parent or c.text,source_uri,dense_score=float(score)) for c,parent,source_uri,score in result]
            except RuntimeError:
                if mode=="dense":raise
                dense=lexical
        if mode=="dense":
            for item in dense[:top_k]:item.score=item.dense_score;item.rerank_score=item.dense_score
            return rewritten,dense[:top_k]
        with tracer.start_as_current_span("rrf_fusion"):
            fused=rrf([lexical,dense]) if mode=="hybrid_raw" else rrf([lexical,dense],weights=[0.75,0.25])
        if mode in {"hybrid_raw","hybrid"}:
            for item in fused[:top_k]:item.rerank_score=item.score
            return rewritten,fused[:top_k]
        rerank_candidates=fused[:self.llm.settings.reranker_candidate_k]
        with tracer.start_as_current_span("rerank"): ranked=await self.llm.rerank(rewritten,rerank_candidates,top_k)
        return rewritten,ranked
