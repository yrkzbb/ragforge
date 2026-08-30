from datetime import datetime,timezone
import json
import re
from pathlib import Path
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
from .models import BuildJob,BuildState,ChangeEvent,Chunk,Document,EvalRun,FeedbackMemory,FeedbackState,KnowledgeBase
from .schemas import ChatRequest,DocumentIngest,EvalRequest,FeedbackCreate,FeedbackReview,KnowledgeBaseCreate,SearchRequest
from .services.llm import LLMService
from .services.retrieval import ndcg_at_k,precision_at_k,recall_at_k,reciprocal_rank
from .services.search import SearchService
from .services.agent import AgentExecutionError,ReActAgent
from .telemetry import AGENT_LATENCY,AGENT_REQUESTS,LLM_COST,TOKEN_USAGE,configure_telemetry
from .worker import compile_knowledge_base

settings=get_settings();tracer=configure_telemetry();app=FastAPI(title="RAGForge API",version="1.0.0",docs_url="/docs")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
FastAPIInstrumentor.instrument_app(app,tracer_provider=trace.get_tracer_provider())

def source_relevance(query:str,text:str)->float:
    """Return a bounded, explainable query/content overlap score for citations."""
    def terms(value:str)->set[str]:
        value=re.sub(r"[^0-9a-z\u4e00-\u9fff]+","",value.lower())
        for stop in ("是什么","有哪些","为什么","怎么","如何","关于","相关","内容","重点","的"):
            value=value.replace(stop,"")
        return {value[i:i+2] for i in range(max(len(value)-1,0)) if value[i:i+2]}
    query_terms=terms(query)
    if not query_terms:return 0.0
    content_terms=terms(text)
    return round(min(1.0,len(query_terms&content_terms)/len(query_terms)),4)

def grounded_sources(query:str,answer:str,contexts:list)->list[dict]:
    no_evidence=("未找到" in answer or "没有找到" in answer) and ("知识库" in answer or "相关内容" in answer)
    if no_evidence:return []
    rows=[]
    for item in contexts:
        text=item.parent_text or item.text
        relevance=source_relevance(query,f"{item.breadcrumb}\n{text}")
        if relevance<0.2:continue
        rows.append({"chunk_id":item.id,"breadcrumb":item.breadcrumb,"source_uri":item.source_uri,"text":text,"relevance":relevance,"retrieval_score":item.rerank_score})
    return sorted(rows,key=lambda row:row["relevance"],reverse=True)[:3]

@app.get("/health")
async def health(db:AsyncSession=Depends(get_db)):
    await db.execute(select(func.now()));return {"status":"ok","service":"ragforge-api"}

@app.get("/metrics",include_in_schema=False)
async def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

@app.get("/api/v1/traces")
async def traces(limit:int=Query(20,ge=1,le=100),service:str="ragforge-api",trace_id:str|None=Query(None,pattern=r"^[0-9a-fA-F]{32}$")):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if trace_id:
                response=await client.get(f"{settings.jaeger_query_url}/api/traces/{trace_id.lower()}")
            else:
                response=await client.get(f"{settings.jaeger_query_url}/api/traces",params={"service":service,"limit":limit})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code==404:
            raise HTTPException(404,"trace not found") from exc
        raise HTTPException(503,f"trace backend unavailable: HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503,f"trace backend unavailable: {type(exc).__name__}") from exc

@app.post("/api/v1/knowledge-bases",status_code=201)
async def create_kb(body:KnowledgeBaseCreate,db:AsyncSession=Depends(get_db)):
    kb=KnowledgeBase(name=body.name);db.add(kb);await db.commit();await db.refresh(kb);return {"id":kb.id,"name":kb.name}

@app.get("/api/v1/dashboard")
async def dashboard(db:AsyncSession=Depends(get_db)):
    knowledge_bases=(await db.scalars(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))).all()
    rows=[]
    for kb in knowledge_bases:
        document_ids=select(Document.id).where(Document.knowledge_base_id==kb.id,Document.active.is_(True))
        document_count=await db.scalar(select(func.count()).select_from(Document).where(Document.knowledge_base_id==kb.id,Document.active.is_(True))) or 0
        chunk_count=await db.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id.in_(document_ids),Chunk.level=="child")) or 0
        pending_events=await db.scalar(select(func.count()).select_from(ChangeEvent).where(ChangeEvent.knowledge_base_id==kb.id,ChangeEvent.consumed.is_(False))) or 0
        last_job=await db.scalar(select(BuildJob).where(BuildJob.knowledge_base_id==kb.id).order_by(BuildJob.created_at.desc()).limit(1))
        rows.append({"id":kb.id,"name":kb.name,"documents":document_count,"chunks":chunk_count,"pending_events":pending_events,"build_state":last_job.state if last_job else None,"image_version":last_job.image_version if last_job else None,"updated_at":last_job.updated_at if last_job else kb.created_at})
    feedback_counts={state.value:await db.scalar(select(func.count()).select_from(FeedbackMemory).where(FeedbackMemory.state==state)) or 0 for state in FeedbackState}
    feedback_counts["injections"]=await db.scalar(select(func.coalesce(func.sum(FeedbackMemory.use_count),0))) or 0
    latest_eval=await db.scalar(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(1))
    return {"knowledge_bases":rows,"totals":{"knowledge_bases":len(rows),"documents":sum(x["documents"] for x in rows),"chunks":sum(x["chunks"] for x in rows),"pending_events":sum(x["pending_events"] for x in rows)},"feedback":feedback_counts,"latest_evaluation":{"dataset_name":latest_eval.dataset_name,"metrics":latest_eval.metrics,"passed":latest_eval.passed,"created_at":latest_eval.created_at} if latest_eval else None}

@app.get("/api/v1/knowledge-bases/{kb_id}/documents")
async def list_documents(kb_id:UUID,db:AsyncSession=Depends(get_db)):
    if not await db.get(KnowledgeBase,kb_id):raise HTTPException(404,"knowledge base not found")
    docs=(await db.scalars(select(Document).where(Document.knowledge_base_id==kb_id,Document.active.is_(True)).order_by(Document.created_at.desc()))).all()
    rows=[]
    for doc in docs:
        chunks=(await db.scalars(select(Chunk).where(Chunk.document_id==doc.id,Chunk.level=="child").order_by(Chunk.ordinal))).all()
        rows.append({"id":doc.id,"title":doc.title,"source_uri":doc.source_uri,"version":doc.version,"created_at":doc.created_at,"original_text":doc.original_text,"metadata":doc.metadata_json,"chunks":[{"id":c.id,"ordinal":c.ordinal,"breadcrumb":c.breadcrumb,"text":c.text,"token_count":c.token_count} for c in chunks]})
    return rows

@app.get("/api/v1/eval-dataset")
async def eval_dataset(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=300)):
    path=Path(__file__).resolve().parents[1]/"eval_data"/"qa.jsonl"
    rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"total":len(rows),"offset":offset,"items":rows[offset:offset+limit]}

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
    rewritten,results=await SearchService(db).search(body.knowledge_base_id,body.query,body.top_k,body.retrieve_k,body.mode)
    return {"query":body.query,"rewritten_query":rewritten,"mode":body.mode,"results":[vars(x) for x in results]}

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
    return [{"id":item.id,"user_id":item.user_id,"knowledge_base_id":item.knowledge_base_id,"correction":item.correction,"reason":item.reason,"scope":item.scope,"confidence":item.confidence,"state":item.state,"source_trace_id":item.source_trace_id,"use_count":item.use_count,"last_used_at":item.last_used_at,"created_at":item.created_at} for item in items]

@app.post("/api/v1/chat")
async def chat(body:ChatRequest,request:Request,db:AsyncSession=Depends(get_db)):
    with AGENT_LATENCY.labels("chat").time(),tracer.start_as_current_span("agent.session") as span:
        span.set_attribute("agent.user_id",body.user_id);span.set_attribute("agent.conversation_id",body.conversation_id or "new")
        try:
            result=await ReActAgent(db,tracer).run(body)
            answer,contexts,memory_items,usage=result.answer,result.contexts,result.memory_items,result.usage
            cost=(usage["input_tokens"]*settings.chat_input_cost_per_million+usage["output_tokens"]*settings.chat_output_cost_per_million)/1_000_000
            for key,value in (("input",usage["input_tokens"]),("output",usage["output_tokens"])):TOKEN_USAGE.labels(key,settings.chat_model).inc(value)
            LLM_COST.labels(settings.chat_model).inc(cost)
            span.set_attribute("agent.iterations",result.iterations)
            span.set_attribute("agent.usage.input_tokens",usage["input_tokens"])
            span.set_attribute("agent.usage.output_tokens",usage["output_tokens"])
            span.set_attribute("agent.usage.estimated_cost_usd",cost)
            AGENT_REQUESTS.labels("chat","ok").inc()
            return {"answer":answer,"sources":grounded_sources(body.message,answer,contexts),"memory_ids":[str(item.id) for item in memory_items],"handoffs":result.handoffs,"iterations":result.iterations,"usage":{**usage,"estimated_cost_usd":cost},"trace_id":format(span.get_span_context().trace_id,"032x")}
        except AgentExecutionError as exc:
            AGENT_REQUESTS.labels("chat","error").inc();span.record_exception(exc);span.set_status(Status(StatusCode.ERROR,str(exc)));raise HTTPException(503,str(exc)) from exc
        except TimeoutError as exc:
            AGENT_REQUESTS.labels("chat","error").inc();span.record_exception(exc);span.set_status(Status(StatusCode.ERROR,"agent node timed out"));raise HTTPException(504,"agent node timed out") from exc
        except Exception as exc:
            AGENT_REQUESTS.labels("chat","error").inc();span.record_exception(exc);span.set_status(Status(StatusCode.ERROR,str(exc)));raise

@app.post("/api/v1/evaluations")
async def evaluate(body:EvalRequest,db:AsyncSession=Depends(get_db)):
    if not await db.get(KnowledgeBase,body.knowledge_base_id):
        raise HTTPException(404,"knowledge base not found")
    active_documents=await db.scalar(select(func.count()).select_from(Document).where(Document.knowledge_base_id==body.knowledge_base_id,Document.active.is_(True))) or 0
    if active_documents==0:
        raise HTTPException(409,"knowledge base has no active documents; compile the benchmark corpus first")
    totals={"recall_at_k":0.0,"precision_at_k":0.0,"mrr":0.0,"ndcg_at_k":0.0};details=[]
    for ex in body.examples:
        _,results=await SearchService(db).search(body.knowledge_base_id,ex.query,body.k,max(body.retrieve_k,body.k),body.mode);ids=[x.id for x in results]
        if ex.relevant_source_uris:ids=list(dict.fromkeys(x.source_uri for x in results));relevant=set(ex.relevant_source_uris)
        else:relevant=set(ex.relevant_chunk_ids)
        scores={"recall_at_k":recall_at_k(ids,relevant,body.k),"precision_at_k":precision_at_k(ids,relevant,body.k),"mrr":reciprocal_rank(ids,relevant),"ndcg_at_k":ndcg_at_k(ids,relevant,body.k)}
        for key,value in scores.items():totals[key]+=value
        details.append({"query":ex.query,**scores})
    metrics={key:round(value/max(len(body.examples),1),6) for key,value in totals.items()};passed=metrics["recall_at_k"]>=.82 and metrics["precision_at_k"]>=.08 and metrics["mrr"]>=.58 and metrics["ndcg_at_k"]>=.70
    run=EvalRun(dataset_name=body.dataset_name,config={"k":body.k,"retrieve_k":body.retrieve_k,"examples":len(body.examples),"mode":body.mode},metrics=metrics,passed=passed);db.add(run);await db.commit()
    return {"run_id":run.id,"mode":body.mode,"passed":passed,"metrics":metrics,"details":details}

@app.get("/api/v1/evaluations")
async def list_evaluations(limit:int=Query(20,ge=1,le=100),db:AsyncSession=Depends(get_db)):
    runs=(await db.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit))).all()
    return [{"id":run.id,"dataset_name":run.dataset_name,"config":run.config,"metrics":run.metrics,"passed":run.passed,"created_at":run.created_at} for run in runs]
