"""Apply idempotent SQL migrations in lexical order."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings


async def main():
    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {row["version"] for row in await connection.fetch("SELECT version FROM schema_migrations")}
        for path in sorted((BACKEND_ROOT / "migrations").glob("*.sql")):
            if path.name in applied:
                continue
            async with connection.transaction():
                await connection.execute(path.read_text(encoding="utf-8"))
                await connection.execute("INSERT INTO schema_migrations(version) VALUES($1)", path.name)
            print(f"applied {path.name}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
