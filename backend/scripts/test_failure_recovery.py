"""Integration probe: a malformed build must retry four attempts and end failed."""
import asyncio
import time
from uuid import UUID

from app.db import SessionLocal
from app.models import BuildJob, BuildState, ChangeEvent, KnowledgeBase
from app.worker import compile_knowledge_base


async def seed():
    async with SessionLocal() as db:
        kb = KnowledgeBase(name=f"failure-recovery-{time.time()}")
        db.add(kb)
        await db.flush()
        db.add(ChangeEvent(
            knowledge_base_id=kb.id, source_uri="test://malformed", operation="upsert",
            payload={"title": "缺少正文"},
        ))
        job = BuildJob(knowledge_base_id=kb.id, image_version=1, state=BuildState.queued)
        db.add(job)
        await db.commit()
        return str(job.id)


async def main():
    job_id = await seed()
    compile_knowledge_base.delay(job_id)
    deadline = time.time() + 120
    while time.time() < deadline:
        async with SessionLocal() as db:
            job = await db.get(BuildJob, UUID(job_id), populate_existing=True)
            state, attempts, error = job.state.value, job.attempts, job.error
        if state == "failed" and attempts == 4:
            print({"state": state, "attempts": attempts, "error": error})
            print("failure_recovery=PASS")
            return
        await asyncio.sleep(1)
    raise AssertionError({"state": state, "attempts": attempts, "error": error})


asyncio.run(main())
