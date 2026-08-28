from datetime import datetime,timezone
from uuid import UUID
from fastapi import Depends,FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import get_settings
from .db import get_db
from .models import BuildJob,BuildState,ChangeEvent,Chunk,EvalRun,FeedbackMemory,FeedbackState,KnowledgeBase
from .schemas import ChatRequest,DocumentIngest,EvalRequest,FeedbackCreate,FeedbackReview,KnowledgeBaseCreate,SearchRequest
from .services.llm import LLMService
from .services.retrieval import ndcg_at_k,precision_at_k,recall_at_k,reciprocal_rank
from .services.search import SearchService
from .telemetry import configure_telemetry
from .worker import compile_knowledge_base

settings=get_settings();tracer=configure_telemetry();app=FastAPI(title="RAGForge API",version="1.0.0",docs_url="/docs")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
FastAPIInstrumentor.instrument_app(app,tracer_provider=trace.get_tracer_provider())

@app.get("/health")
async def health(db:AsyncSession=Depends(get_db)):
    await db.execute(select(func.now()));return {"status":"ok","service":"ragforge-api"}

@app.post("/api/v1/knowledge-bases",status_code=201)
async def create_kb(body:KnowledgeBaseCreate,db:AsyncSession=Depends(get_db)):
    kb=KnowledgeBase(name=body.name);db.add(kb);await db.commit();await db.refresh(kb);return {"id":kb.id,"name":kb.name}

@app.post("/api/v1/knowledge-bases/{kb_id}/documents",status_code=202)
async def ingest(kb_id:UUID,body:DocumentIngest,db:AsyncSession=Depends(get_db)):
    if not await db.get(KnowledgeBase,kb_id):raise HTTPException(404,"knowledge base not found")
    event=ChangeEvent(knowledge_base_id=kb_id,source_uri=body.source_uri,operation="upsert",payload=body.model_dump())
    db.add(event);await db.commit();return {"event_id":event.id,"status":"recorded"}

@app.post("/api/v1/knowledge-bases/{kb_id}/compile",status_code=202)
async def compile_kb(kb_id:UUID,db:AsyncSession=Depends(get_db)):
    version=(await db.scalar(select(func.coalesce(func.max(BuildJob.image_version),0)).where(BuildJob.knowledge_base_id==kb_id)))+1
    job=BuildJob(knowledge_base_id=kb_id,image_version=version,state=BuildState.queued);db.add(job);await db.commit();compile_knowledge_base.apply_async(args=[str(job.id)],countdown=settings.compile_debounce_seconds)
    return {"job_id":job.id,"image_version":version,"status":"queued"}

@app.get("/api/v1/build-jobs/{job_id}")
async def build_status(job_id:UUID,db:AsyncSession=Depends(get_db)):
    job=await db.get(BuildJob,job_id)
    if not job:raise HTTPException(404,"job not found")
    return {"id":job.id,"state":job.state,"attempts":job.attempts,"error":job.error,"image_version":job.image_version}

@app.post("/api/v1/search")
async def search(body:SearchRequest,db:AsyncSession=Depends(get_db)):
    rewritten,results=await SearchService(db).search(body.knowledge_base_id,body.query,body.top_k,body.retrieve_k)
    return {"query":body.query,"rewritten_query":rewritten,"results":[vars(x) for x in results]}

@app.post("/api/v1/feedback",status_code=201)
async def create_feedback(body:FeedbackCreate,db:AsyncSession=Depends(get_db)):
    item=FeedbackMemory(**body.model_dump());db.add(item);await db.commit();await db.refresh(item);return {"id":item.id,"state":item.state}

@app.patch("/api/v1/feedback/{item_id}")
async def review_feedback(item_id:UUID,body:FeedbackReview,db:AsyncSession=Depends(get_db)):
    item=await db.get(FeedbackMemory,item_id)
    if not item:raise HTTPException(404,"feedback not found")
    item.state=FeedbackState.accepted if body.accepted else FeedbackState.rejected;item.reviewed_at=datetime.now(timezone.utc)
    if body.accepted:
        try:item.embedding=(await LLMService().embed([item.correction]))[0]
        except RuntimeError:pass
    await db.commit();return {"id":item.id,"state":item.state}

@app.post("/api/v1/chat")
async def chat(body:ChatRequest,request:Request,db:AsyncSession=Depends(get_db)):
    with tracer.start_as_current_span("agent.session") as span:
        span.set_attribute("agent.user_id",body.user_id);span.set_attribute("agent.conversation_id",body.conversation_id or "new")
        _,contexts=await SearchService(db).search(body.knowledge_base_id,body.message,8,30)
        memories=(await db.scalars(select(FeedbackMemory.correction).where(FeedbackMemory.user_id==body.user_id,FeedbackMemory.state==FeedbackState.accepted).limit(5))).all()
        with tracer.start_as_current_span("llm.generate") as llm_span:
            answer,usage=await LLMService().answer(body.message,contexts,list(memories));llm_span.set_attribute("llm.token.input",usage["input_tokens"]);llm_span.set_attribute("llm.token.output",usage["output_tokens"])
        return {"answer":answer,"sources":[{"chunk_id":c.id,"breadcrumb":c.breadcrumb,"score":c.rerank_score} for c in contexts],"usage":usage,"trace_id":format(span.get_span_context().trace_id,"032x")}

@app.post("/api/v1/evaluations")
async def evaluate(body:EvalRequest,db:AsyncSession=Depends(get_db)):
    totals={"recall_at_k":0.0,"precision_at_k":0.0,"mrr":0.0,"ndcg_at_k":0.0};details=[]
    for ex in body.examples:
        _,results=await SearchService(db).search(body.knowledge_base_id,ex.query,body.k,max(30,body.k));ids=[x.id for x in results];relevant=set(ex.relevant_chunk_ids)
        scores={"recall_at_k":recall_at_k(ids,relevant,body.k),"precision_at_k":precision_at_k(ids,relevant,body.k),"mrr":reciprocal_rank(ids,relevant),"ndcg_at_k":ndcg_at_k(ids,relevant,body.k)}
        for key,value in scores.items():totals[key]+=value
        details.append({"query":ex.query,**scores})
    metrics={key:value/max(len(body.examples),1) for key,value in totals.items()};passed=metrics["recall_at_k"]>=.82 and metrics["mrr"]>=.58 and metrics["ndcg_at_k"]>=.70
    run=EvalRun(dataset_name=body.dataset_name,config={"k":body.k,"examples":len(body.examples)},metrics=metrics,passed=passed);db.add(run);await db.commit()
    return {"run_id":run.id,"passed":passed,"metrics":metrics,"details":details}

