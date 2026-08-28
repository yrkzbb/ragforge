from datetime import datetime,timezone
from uuid import UUID
from fastapi import Depends,FastAPI,HTTPException,Request,Query
from fastapi.responses import Response
import httpx
from prometheus_client import CONTENT_TYPE_LATEST,generate_latest
from opentelemetry.trace import Status,StatusCode
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
from .services.memory import FeedbackMemoryService
from .telemetry import AGENT_LATENCY,AGENT_REQUESTS,LLM_COST,TOKEN_USAGE,configure_telemetry
from .worker import compile_knowledge_base

settings=get_settings();tracer=configure_telemetry();app=FastAPI(title="RAGForge API",version="1.0.0",docs_url="/docs")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
FastAPIInstrumentor.instrument_app(app,tracer_provider=trace.get_tracer_provider())

@app.get("/health")
async def health(db:AsyncSession=Depends(get_db)):
    await db.execute(select(func.now()));return {"status":"ok","service":"ragforge-api"}

@app.get("/metrics",include_in_schema=False)
async def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

@app.get("/api/v1/traces")
async def traces(limit:int=Query(20,ge=1,le=100),service:str="ragforge-api"):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response=await client.get(f"{settings.jaeger_query_url}/api/traces",params={"service":service,"limit":limit})
            response.raise_for_status();return response.json()
    except httpx.HTTPError as exc:raise HTTPException(503,f"trace backend unavailable: {type(exc).__name__}") from exc

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

@app.get("/api/v1/build-jobs")
async def list_build_jobs(limit:int=Query(20,ge=1,le=100),db:AsyncSession=Depends(get_db)):
    jobs=(await db.scalars(select(BuildJob).order_by(BuildJob.created_at.desc()).limit(limit))).all()
    return [{"id":job.id,"knowledge_base_id":job.knowledge_base_id,"state":job.state,"attempts":job.attempts,"error":job.error,"image_version":job.image_version,"created_at":job.created_at} for job in jobs]

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

@app.get("/api/v1/feedback")
async def list_feedback(limit:int=Query(50,ge=1,le=200),db:AsyncSession=Depends(get_db)):
    items=(await db.scalars(select(FeedbackMemory).order_by(FeedbackMemory.created_at.desc()).limit(limit))).all()
    return [{"id":item.id,"user_id":item.user_id,"knowledge_base_id":item.knowledge_base_id,"correction":item.correction,"reason":item.reason,"scope":item.scope,"confidence":item.confidence,"state":item.state,"created_at":item.created_at} for item in items]

@app.post("/api/v1/chat")
async def chat(body:ChatRequest,request:Request,db:AsyncSession=Depends(get_db)):
    with AGENT_LATENCY.labels("chat").time(),tracer.start_as_current_span("agent.session") as span:
        span.set_attribute("agent.user_id",body.user_id);span.set_attribute("agent.conversation_id",body.conversation_id or "new")
        try:
            with tracer.start_as_current_span("tool.call") as tool_span:
                tool_span.set_attribute("tool.name","knowledge_base_search")
                tool_span.set_attribute("tool.type","retrieval")
                _,contexts=await SearchService(db).search(body.knowledge_base_id,body.message,8,30)
                tool_span.set_attribute("tool.result.count",len(contexts))
            memory_items=await FeedbackMemoryService(db).select_for_chat(body.user_id,body.knowledge_base_id,body.message)
            memories=[f"适用范围：{item.scope}；纠正：{item.correction}；原因：{item.reason}" for item in memory_items]
            with tracer.start_as_current_span("llm.generate") as llm_span:
                answer,usage=await LLMService().answer(body.message,contexts,list(memories))
                cost=(usage["input_tokens"]*settings.chat_input_cost_per_million+usage["output_tokens"]*settings.chat_output_cost_per_million)/1_000_000
                for key,value in (("input",usage["input_tokens"]),("output",usage["output_tokens"])):TOKEN_USAGE.labels(key,settings.chat_model).inc(value)
                LLM_COST.labels(settings.chat_model).inc(cost)
                llm_span.set_attribute("llm.token.input",usage["input_tokens"]);llm_span.set_attribute("llm.token.output",usage["output_tokens"]);llm_span.set_attribute("llm.cost.usd",cost)
            AGENT_REQUESTS.labels("chat","ok").inc()
            return {"answer":answer,"sources":[{"chunk_id":c.id,"breadcrumb":c.breadcrumb,"score":c.rerank_score} for c in contexts],"memory_ids":[str(item.id) for item in memory_items],"usage":{**usage,"estimated_cost_usd":cost},"trace_id":format(span.get_span_context().trace_id,"032x")}
        except Exception as exc:
            AGENT_REQUESTS.labels("chat","error").inc();span.record_exception(exc);span.set_status(Status(StatusCode.ERROR,str(exc)));raise

@app.post("/api/v1/evaluations")
async def evaluate(body:EvalRequest,db:AsyncSession=Depends(get_db)):
    totals={"recall_at_k":0.0,"precision_at_k":0.0,"mrr":0.0,"ndcg_at_k":0.0};details=[]
    for ex in body.examples:
        _,results=await SearchService(db).search(body.knowledge_base_id,ex.query,body.k,max(30,body.k));ids=[x.id for x in results]
        if ex.relevant_source_uris:ids=list(dict.fromkeys(x.source_uri for x in results));relevant=set(ex.relevant_source_uris)
        else:relevant=set(ex.relevant_chunk_ids)
        scores={"recall_at_k":recall_at_k(ids,relevant,body.k),"precision_at_k":precision_at_k(ids,relevant,body.k),"mrr":reciprocal_rank(ids,relevant),"ndcg_at_k":ndcg_at_k(ids,relevant,body.k)}
        for key,value in scores.items():totals[key]+=value
        details.append({"query":ex.query,**scores})
    metrics={key:round(value/max(len(body.examples),1),6) for key,value in totals.items()};passed=metrics["recall_at_k"]>=.82 and metrics["precision_at_k"]>=.08 and metrics["mrr"]>=.58 and metrics["ndcg_at_k"]>=.70
    run=EvalRun(dataset_name=body.dataset_name,config={"k":body.k,"examples":len(body.examples)},metrics=metrics,passed=passed);db.add(run);await db.commit()
    return {"run_id":run.id,"passed":passed,"metrics":metrics,"details":details}

@app.get("/api/v1/evaluations")
async def list_evaluations(limit:int=Query(20,ge=1,le=100),db:AsyncSession=Depends(get_db)):
    runs=(await db.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit))).all()
    return [{"id":run.id,"dataset_name":run.dataset_name,"config":run.config,"metrics":run.metrics,"passed":run.passed,"created_at":run.created_at} for run in runs]
