"""V4 Phase 0 P0-5 migration: 为 reference_packs 表追加 26 个新字段

新增字段：
- 2 个 V4.1 维度 JSON 字段（bridges_json, character_archive_json）
- 24 个 V4.4 K5 三档预压缩字段（8 维度 × 3 档位）

SQLite 支持 ALTER TABLE ADD COLUMN，所有字段都是 nullable TEXT，零数据迁移风险。
幂等：检测字段已存在则跳过。
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.database import get_engine

logger = logging.getLogger(__name__)


NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    # V4.1 新维度 JSON 字段
    ("bridges_json", "TEXT"),
    ("character_archive_json", "TEXT"),

    # V4.4 K5 三档预压缩字段（8 维度 × 3 档 = 24 个）
    ("methodology_light", "TEXT"),
    ("methodology_medium", "TEXT"),
    ("methodology_deep", "TEXT"),

    ("style_light", "TEXT"),
    ("style_medium", "TEXT"),
    ("style_deep", "TEXT"),

    ("structure_light", "TEXT"),
    ("structure_medium", "TEXT"),
    ("structure_deep", "TEXT"),

    ("archetypes_light", "TEXT"),
    ("archetypes_medium", "TEXT"),
    ("archetypes_deep", "TEXT"),

    ("worldbuilding_light", "TEXT"),
    ("worldbuilding_medium", "TEXT"),
    ("worldbuilding_deep", "TEXT"),

    ("synopsis_light", "TEXT"),
    ("synopsis_medium", "TEXT"),
    ("synopsis_deep", "TEXT"),

    ("bridges_light", "TEXT"),
    ("bridges_medium", "TEXT"),
    ("bridges_deep", "TEXT"),

    ("character_archive_light", "TEXT"),
    ("character_archive_medium", "TEXT"),
    ("character_archive_deep", "TEXT"),
)


async def get_existing_columns(conn) -> set[str]:
    """查询 reference_packs 表当前已有的列名集合。"""
    result = await conn.execute(text("PRAGMA table_info(reference_packs)"))
    return {row[1] for row in result.fetchall()}


async def run() -> None:
    engine = await get_engine("v4_phase0_p05_migration")

    async with engine.begin() as conn:
        existing = await get_existing_columns(conn)
        logger.info("[V4 P0-5 migration] current columns: %d", len(existing))

        added = 0
        skipped = 0
        for col_name, col_type in NEW_COLUMNS:
            if col_name in existing:
                skipped += 1
                continue
            await conn.execute(
                text(f"ALTER TABLE reference_packs ADD COLUMN {col_name} {col_type}")
            )
            added += 1

        logger.info(
            "[V4 P0-5 migration] done: %d added, %d skipped (already present)",
            added, skipped,
        )

        # 验证
        final = await get_existing_columns(conn)
        new_present = sum(1 for col, _ in NEW_COLUMNS if col in final)
        assert new_present == len(NEW_COLUMNS), (
            f"expected all {len(NEW_COLUMNS)} new columns, found {new_present}"
        )

    print(f"[V4 P0-5 migration] reference_packs +{added} columns "
          f"(skipped {skipped}), total {len(final)} columns")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())
