"""V4 Phase 2 P2-1 migration: K2 桥段四章结构数据模型

新增：
- plot_bridges 表（PlotBridge model 对应）
- chapter_outlines 加 3 字段：bridge_id / bridge_position / position_constraints

幂等：表已存在或字段已存在则跳过。SQLite 的 CREATE TABLE 和 ADD COLUMN 都不破坏现有数据。
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.database import get_engine
from app.db_base import Base

logger = logging.getLogger(__name__)


CHAPTER_OUTLINE_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("bridge_id", "VARCHAR(36)"),
    ("bridge_position", "VARCHAR(20)"),
    ("position_constraints", "TEXT"),
)


async def get_existing_columns(conn, table: str) -> set[str]:
    """查询某表当前已有的列名集合。"""
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


async def get_existing_tables(conn) -> set[str]:
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    return {row[0] for row in result.fetchall()}


async def run() -> None:
    # 触发 model 加载（确保 plot_bridges 在 Base.metadata 中）
    from app.models.plot_bridge import PlotBridge  # noqa: F401

    engine = await get_engine("v4_phase2_p21_migration")

    # 1. 创建 plot_bridges 表（如不存在）
    async with engine.begin() as conn:
        existing_tables = await get_existing_tables(conn)
        if "plot_bridges" not in existing_tables:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.tables["plot_bridges"]
                .create(sync_conn, checkfirst=True)
            )
            logger.info("[V4 P2-1 migration] CREATED table plot_bridges")
        else:
            logger.info("[V4 P2-1 migration] plot_bridges already exists, skip")

    # 2. 给 chapter_outlines 加 3 个字段
    async with engine.begin() as conn:
        existing = await get_existing_columns(conn, "chapter_outlines")
        added = 0
        skipped = 0
        for col_name, col_type in CHAPTER_OUTLINE_NEW_COLUMNS:
            if col_name in existing:
                skipped += 1
                continue
            await conn.execute(
                text(f"ALTER TABLE chapter_outlines ADD COLUMN {col_name} {col_type}")
            )
            added += 1

        logger.info(
            "[V4 P2-1 migration] chapter_outlines: %d added, %d skipped",
            added, skipped,
        )

    # 3. 验证
    async with engine.begin() as conn:
        tables = await get_existing_tables(conn)
        co_cols = await get_existing_columns(conn, "chapter_outlines")
        assert "plot_bridges" in tables, "plot_bridges 创建失败"
        missing = [c for c, _ in CHAPTER_OUTLINE_NEW_COLUMNS if c not in co_cols]
        assert not missing, f"chapter_outlines 字段缺失: {missing}"

    print("[V4 P2-1 migration] done: plot_bridges + chapter_outlines 3 fields OK")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())
