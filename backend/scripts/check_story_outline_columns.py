"""Inspect story_outlines table columns"""
import asyncio
import os
from urllib.parse import urlparse

import asyncpg


def get_db_config():
    db_url = os.getenv("DATABASE_URL", "postgresql://mumuai:mumuai123@localhost:5432/mumuai_novel")
    parsed = urlparse(db_url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


async def main():
    cfg = get_db_config()
    conn = await asyncpg.connect(**cfg)
    try:
        rows = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'story_outlines'
            ORDER BY ordinal_position
            """
        )
        print("story_outlines columns:")
        for row in rows:
            print(f"- {row['column_name']}: {row['data_type']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
