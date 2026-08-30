import asyncio
import hashlib
import socket
from datetime import datetime,timedelta,timezone
from uuid import UUID
from celery import Celery
from sqlalchemy import select,update
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from .config import get_settings
from .models import BuildJob,BuildState,ChangeEvent,Chunk,Document
from .services.chunking import embedding_text,parent_child_chunks
from .services.llm import LLMService

settings=get_settings();celery_app=Celery("ragforge",broker=settings.redis_url,backend=settings.redis_url)
celery_app.conf.update(task_acks_late=True,worker_prefetch_multiplier=1,task_track_started=True)

async def _compile(job_id:str):
    worker=f"{socket.gethostname()}:{job_id[:8]}";now=datetime.now(timezone.utc)
    engine=create_async_engine(settings.database_url,pool_pre_ping=True)
    task_session=async_sessionmaker(engine,expire_on_commit=False)
    try:
      async with task_session() as db:
        # Atomic compare-and-swap lease: only queued/expired jobs can transition to leased.
        claim=await db.execute(update(BuildJob).where(BuildJob.id==UUID(job_id),BuildJob.attempts<4,((BuildJob.state==BuildState.queued)|(BuildJob.state==BuildState.failed)|(BuildJob.lease_expires_at<now))).values(state=BuildState.leased,lease_owner=worker,lease_expires_at=now+timedelta(seconds=settings.worker_lease_seconds),attempts=BuildJob.attempts+1,error=None).returning(BuildJob.id))
        if not claim.scalar_one_or_none():return {"status":"not_acquired"}
        await db.commit();job=await db.get(BuildJob,UUID(job_id));job.state=BuildState.running;await db.commit()
        try:
            events=(await db.scalars(select(ChangeEvent).where(ChangeEvent.knowledge_base_id==job.knowledge_base_id,ChangeEvent.consumed.is_(False)).order_by(ChangeEvent.created_at))).all()
            latest={e.source_uri:e for e in events}
            llm=LLMService();processed=0
            for event in latest.values():
                if event.operation=="delete":
                    await db.execute(update(Document).where(Document.knowledge_base_id==job.knowledge_base_id,Document.source_uri==event.source_uri,Document.active.is_(True)).values(active=False))
                    continue
                payload=event.payload;text=payload["text"];digest=hashlib.sha256(text.encode()).hexdigest()
                existing=await db.scalar(select(Document).where(Document.knowledge_base_id==job.knowledge_base_id,Document.source_uri==event.source_uri,Document.content_hash==digest,Document.active.is_(True)))
                if existing:continue
                previous=(await db.scalars(select(Document).where(Document.knowledge_base_id==job.knowledge_base_id,Document.source_uri==event.source_uri,Document.active.is_(True)))).all()
                next_version=max((item.version for item in previous),default=0)+1
                for item in previous:item.active=False
                doc=Document(knowledge_base_id=job.knowledge_base_id,source_uri=event.source_uri,title=payload["title"],original_text=text,content_hash=digest,version=next_version,active=True,metadata_json=payload.get("metadata",{}));db.add(doc);await db.flush()
                drafts=parent_child_chunks(text,payload["title"]);parent_map={};children=[]
                for draft in drafts:
                    chunk=Chunk(document_id=doc.id,ordinal=draft.ordinal,level=draft.level,breadcrumb=draft.breadcrumb,text=draft.text,token_count=len(draft.text))
                    if draft.level=="parent":db.add(chunk);await db.flush();parent_map[draft.ordinal]=chunk.id
                    else:chunk.parent_id=parent_map[draft.parent_ordinal];children.append(chunk);db.add(chunk)
                await db.flush()
                try:
                    vectors=await llm.embed([embedding_text(c.breadcrumb,c.text) for c in children])
                    for chunk,vector in zip(children,vectors):chunk.embedding=vector
                except RuntimeError:pass
                processed+=1
            for event in events:event.consumed=True
            job.state=BuildState.succeeded;job.lease_owner=None;job.lease_expires_at=None;await db.commit()
            return {"status":"succeeded","documents":processed}
        except Exception as exc:
            job.state=BuildState.failed;job.error=str(exc)[:2000];await db.commit();raise
    finally:
        await engine.dispose()

@celery_app.task(bind=True,autoretry_for=(Exception,),retry_backoff=True,retry_kwargs={"max_retries":3})
def compile_knowledge_base(self,job_id:str):return asyncio.run(_compile(job_id))
