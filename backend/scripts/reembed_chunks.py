"""Rebuild active child-chunk embeddings with title hierarchy included."""
from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Chunk, Document, KnowledgeBase
from app.services.chunking import embedding_text
from app.services.llm import LLMService


async def reembed(knowledge_base_id: UUID, batch_size: int) -> None:
    llm = LLMService()
    async with SessionLocal() as db:
        knowledge_base = await db.get(KnowledgeBase, knowledge_base_id)
        if not knowledge_base:
            raise SystemExit(f"knowledge base not found: {knowledge_base_id}")

        condition = (
            Document.knowledge_base_id == knowledge_base_id,
            Document.active.is_(True),
            Chunk.level == "child",
        )
        total = await db.scalar(
            select(func.count()).select_from(Chunk).join(Document).where(*condition)
        ) or 0
        processed = 0
        while processed < total:
            chunks = (await db.scalars(
                select(Chunk)
                .join(Document)
                .where(*condition)
                .order_by(Chunk.id)
                .offset(processed)
                .limit(batch_size)
            )).all()
            if not chunks:
                break
            vectors = await llm.embed([
                embedding_text(chunk.breadcrumb, chunk.text) for chunk in chunks
            ])
            if len(vectors) != len(chunks):
                raise RuntimeError("embedding response count does not match chunk count")
            for chunk, vector in zip(chunks, vectors):
                chunk.embedding = vector
            await db.commit()
            processed += len(chunks)
            print(f"re-embedded {processed}/{total} child chunks", flush=True)

        embedded = await db.scalar(
            select(func.count()).select_from(Chunk).join(Document).where(
                *condition, Chunk.embedding.is_not(None)
            )
        ) or 0
        print({
            "knowledge_base_id": str(knowledge_base_id),
            "knowledge_base": knowledge_base.name,
            "child_chunks": total,
            "embedded_chunks": embedded,
        })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-base-id", required=True, type=UUID)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size must be between 1 and 500")
    asyncio.run(reembed(args.knowledge_base_id, args.batch_size))


if __name__ == "__main__":
    main()
