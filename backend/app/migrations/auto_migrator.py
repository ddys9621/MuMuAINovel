"""Auto migration utilities to keep DB schema in sync on startup."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.logger import get_logger

logger = get_logger(__name__)


async def column_exists(conn, table: str, column: str) -> bool:
    result = await conn.execute(
        text(f"PRAGMA table_info({table})")
    )
    rows = result.fetchall()
    return any(row.name == column for row in rows)


async def apply_sql(conn, statements: Iterable[str]):
    for stmt in statements:
        logger.info("📄 Executing migration SQL: %s", stmt.split("\n", 1)[0])
        await conn.execute(text(stmt))


async def ensure_chapter_outline_columns(engine: AsyncEngine):
    """Ensure chapter_outline_id columns exist on chapters and plot_cards."""
    async with engine.begin() as conn:
        # chapters table
        if not await column_exists(conn, "chapters", "chapter_outline_id"):
            logger.info("🔧 Adding chapters.chapter_outline_id column")
            await apply_sql(conn, [
                """ALTER TABLE chapters
                ADD COLUMN chapter_outline_id VARCHAR(36) NULL""",
                """CREATE INDEX IF NOT EXISTS idx_chapters_chapter_outline_id
                ON chapters (chapter_outline_id)""",
            ])
            try:
                await conn.execute(text(
                    """ALTER TABLE chapters
                    ADD CONSTRAINT fk_chapters_chapter_outline
                    FOREIGN KEY (chapter_outline_id)
                    REFERENCES chapter_outlines (id)
                    ON DELETE SET NULL"""
                ))
            except Exception:
                pass  # SQLite does not support ADD CONSTRAINT in ALTER TABLE
        else:
            logger.info("✅ chapters.chapter_outline_id already exists")

        # plot_cards table
        if not await column_exists(conn, "plot_cards", "chapter_outline_id"):
            logger.info("🔧 Adding plot_cards.chapter_outline_id column")
            await apply_sql(conn, [
                """ALTER TABLE plot_cards
                ADD COLUMN chapter_outline_id VARCHAR(36) NULL""",
                """CREATE INDEX IF NOT EXISTS idx_plot_cards_chapter_outline_id
                ON plot_cards (chapter_outline_id)""",
            ])
            try:
                await conn.execute(text(
                    """ALTER TABLE plot_cards
                    ADD CONSTRAINT fk_plot_cards_chapter_outline
                    FOREIGN KEY (chapter_outline_id)
                    REFERENCES chapter_outlines (id)
                    ON DELETE SET NULL"""
                ))
            except Exception:
                pass  # SQLite does not support ADD CONSTRAINT in ALTER TABLE
        else:
            logger.info("✅ plot_cards.chapter_outline_id already exists")


async def ensure_story_outline_columns(engine: AsyncEngine):
    """Ensure new columns exist on story_outlines table."""
    async with engine.begin() as conn:
        if not await column_exists(conn, "story_outlines", "status"):
            logger.info("🔧 Adding story_outlines.status column")
            await apply_sql(conn, [
                """ALTER TABLE story_outlines
                ADD COLUMN status VARCHAR(20) DEFAULT 'published'""",
                """UPDATE story_outlines
                SET status = 'published'
                WHERE status IS NULL""",
            ])
        else:
            logger.info("✅ story_outlines.status already exists")

        if not await column_exists(conn, "story_outlines", "editor_id"):
            logger.info("🔧 Adding story_outlines.editor_id column")
            await apply_sql(conn, [
                """ALTER TABLE story_outlines
                ADD COLUMN editor_id VARCHAR(36)""",
            ])
        else:
            logger.info("✅ story_outlines.editor_id already exists")



async def ensure_plot_line_link_columns(engine: AsyncEngine):
    """Ensure new columns exist on chapter_outline_plot_line_links table."""
    async with engine.begin() as conn:
        if not await column_exists(conn, "chapter_outline_plot_line_links", "timeline_coverage"):
            logger.info("🔧 Adding chapter_outline_plot_line_links.timeline_coverage column")
            await apply_sql(conn, [
                """ALTER TABLE chapter_outline_plot_line_links
                ADD COLUMN timeline_coverage TEXT""",
            ])
        else:
            logger.info("✅ chapter_outline_plot_line_links.timeline_coverage already exists")


async def ensure_plot_line_columns(engine: AsyncEngine):
    """Ensure new columns exist on plot_lines table."""
    async with engine.begin() as conn:
        if not await column_exists(conn, "plot_lines", "estimated_chapters"):
            logger.info("🔧 Adding plot_lines.estimated_chapters column")
            await apply_sql(conn, [
                """ALTER TABLE plot_lines
                ADD COLUMN estimated_chapters INTEGER""",
            ])
            try:
                await conn.execute(text(
                    """COMMENT ON COLUMN plot_lines.estimated_chapters IS '预计章节数：完成这条剧情线预计需要的章节数量'"""
                ))
            except Exception:
                pass  # SQLite does not support COMMENT ON COLUMN
            # 为已有数据设置默认值
            logger.info("🔧 Setting default values for existing plot_lines")
            await apply_sql(conn, [
                """UPDATE plot_lines
                SET estimated_chapters = CASE
                    WHEN line_type = 'main' THEN 40
                    WHEN line_type = 'sub' THEN 15
                    ELSE 8
                END
                WHERE estimated_chapters IS NULL""",
            ])
        else:
            logger.info("✅ plot_lines.estimated_chapters already exists")


async def ensure_chapter_outline_scene_pov_columns(engine: AsyncEngine):
    """Ensure scene and pov columns exist on chapter_outlines table (专业网文版升级)."""
    async with engine.begin() as conn:
        # scene 字段
        if not await column_exists(conn, "chapter_outlines", "scene"):
            logger.info("🔧 Adding chapter_outlines.scene column (专业网文版)")
            await apply_sql(conn, [
                """ALTER TABLE chapter_outlines
                ADD COLUMN scene VARCHAR(200)""",
            ])
            try:
                await conn.execute(text(
                    """COMMENT ON COLUMN chapter_outlines.scene IS '场景地点，如拳击场→后台'"""
                ))
            except Exception:
                pass  # SQLite does not support COMMENT ON COLUMN
        else:
            logger.info("✅ chapter_outlines.scene already exists")

        # pov 字段
        if not await column_exists(conn, "chapter_outlines", "pov"):
            logger.info("🔧 Adding chapter_outlines.pov column (专业网文版)")
            await apply_sql(conn, [
                """ALTER TABLE chapter_outlines
                ADD COLUMN pov VARCHAR(100)""",
            ])
            try:
                await conn.execute(text(
                    """COMMENT ON COLUMN chapter_outlines.pov IS '视角角色名'"""
                ))
            except Exception:
                pass  # SQLite does not support COMMENT ON COLUMN
        else:
            logger.info("✅ chapter_outlines.pov already exists")


async def ensure_plot_cards_scene_columns(engine: AsyncEngine):
    """Ensure scene generation columns exist on plot_cards table (场景级创作循环)."""
    async with engine.begin() as conn:
        # generation_status 字段
        if not await column_exists(conn, "plot_cards", "generation_status"):
            logger.info("🔧 Adding plot_cards.generation_status column (场景级创作)")
            await apply_sql(conn, [
                """ALTER TABLE plot_cards
                ADD COLUMN generation_status VARCHAR(20) DEFAULT 'pending'""",
            ])
        else:
            logger.info("✅ plot_cards.generation_status already exists")

        # generated_content 字段
        if not await column_exists(conn, "plot_cards", "generated_content"):
            logger.info("🔧 Adding plot_cards.generated_content column (场景级创作)")
            await apply_sql(conn, [
                """ALTER TABLE plot_cards
                ADD COLUMN generated_content TEXT""",
            ])
        else:
            logger.info("✅ plot_cards.generated_content already exists")

        # word_count_target 字段
        if not await column_exists(conn, "plot_cards", "word_count_target"):
            logger.info("🔧 Adding plot_cards.word_count_target column (场景级创作)")
            await apply_sql(conn, [
                """ALTER TABLE plot_cards
                ADD COLUMN word_count_target INTEGER DEFAULT 500""",
            ])
        else:
            logger.info("✅ plot_cards.word_count_target already exists")

        # word_count_actual 字段
        if not await column_exists(conn, "plot_cards", "word_count_actual"):
            logger.info("🔧 Adding plot_cards.word_count_actual column (场景级创作)")
            await apply_sql(conn, [
                """ALTER TABLE plot_cards
                ADD COLUMN word_count_actual INTEGER DEFAULT 0""",
            ])
        else:
            logger.info("✅ plot_cards.word_count_actual already exists")

        # generation_order 字段
        if not await column_exists(conn, "plot_cards", "generation_order"):
            logger.info("🔧 Adding plot_cards.generation_order column (场景级创作)")
            await apply_sql(conn, [
                """ALTER TABLE plot_cards
                ADD COLUMN generation_order INTEGER DEFAULT 0""",
            ])
        else:
            logger.info("✅ plot_cards.generation_order already exists")


async def ensure_book_dissect_v2_columns(engine: AsyncEngine):
    """Ensure V2 columns exist on book_dissect_tasks table.

    V2 字段：
    - version (int, default=1)
    - extraction_phase (varchar 50)
    - chapters_total / chapters_extracted / chapters_failed (int, default=0)
    - sampling_mode (varchar 20, default='all')
    - sampling_param (int, default=1)
    """
    v2_columns = [
        ("version", "INTEGER DEFAULT 1"),
        ("extraction_phase", "VARCHAR(50)"),
        ("chapters_total", "INTEGER DEFAULT 0"),
        ("chapters_extracted", "INTEGER DEFAULT 0"),
        ("chapters_failed", "INTEGER DEFAULT 0"),
        ("sampling_mode", "VARCHAR(20) DEFAULT 'all'"),
        ("sampling_param", "INTEGER DEFAULT 1"),
    ]

    async with engine.begin() as conn:
        for col_name, col_def in v2_columns:
            if not await column_exists(conn, "book_dissect_tasks", col_name):
                logger.info("🔧 Adding book_dissect_tasks.%s column (V2)", col_name)
                await apply_sql(conn, [
                    f"ALTER TABLE book_dissect_tasks ADD COLUMN {col_name} {col_def}",
                ])
            else:
                logger.info("✅ book_dissect_tasks.%s already exists", col_name)

        # 既有任务统一标记为 V1（version=1 是默认值，但显式刷一次确保正确）
        await apply_sql(conn, [
            "UPDATE book_dissect_tasks SET version = 1 WHERE version IS NULL",
        ])


async def ensure_book_dissect_v31_columns(engine: AsyncEngine):
    """Ensure V3.1 columns exist on book_dissect_tasks table.

    V3.1 字段：
    - extraction_engine (varchar 20, default='auto')
      路由策略：auto(由 LongContextRouter 决定) / chunked(强制逐章) / long_context(强制一次性)
    """
    v31_columns = [
        ("extraction_engine", "VARCHAR(20) DEFAULT 'auto'"),
    ]

    async with engine.begin() as conn:
        for col_name, col_def in v31_columns:
            if not await column_exists(conn, "book_dissect_tasks", col_name):
                logger.info("🔧 Adding book_dissect_tasks.%s column (V3.1)", col_name)
                await apply_sql(conn, [
                    f"ALTER TABLE book_dissect_tasks ADD COLUMN {col_name} {col_def}",
                ])
            else:
                logger.info("✅ book_dissect_tasks.%s already exists", col_name)


async def ensure_reference_pack_v32_columns(engine: AsyncEngine):
    """Ensure V3.2 columns exist on reference_packs table.

    V3.2 字段（synopsis 复活 + V3.2-P2 模式三维度）：
    - synopsis_json (TEXT, NULL) Tab6 故事类型骨架（Story Bible）
    - entities_json / relations_json / events_json (TEXT, NULL) V3.2-P2 聚合模式三维度
      见 @/agent-docs/features/dissect_to_creation_pipeline.md §A.6 / §A.7
    """
    v32_columns = [
        ("synopsis_json", "TEXT NULL"),
        # V3.2-P2：聚合模式三维度（不调 LLM，从 V2 表纯统计聚合产出）
        ("entities_json", "TEXT NULL"),
        ("relations_json", "TEXT NULL"),
        ("events_json", "TEXT NULL"),
    ]

    async with engine.begin() as conn:
        for col_name, col_def in v32_columns:
            if not await column_exists(conn, "reference_packs", col_name):
                logger.info("🔧 Adding reference_packs.%s column (V3.2)", col_name)
                await apply_sql(conn, [
                    f"ALTER TABLE reference_packs ADD COLUMN {col_name} {col_def}",
                ])
            else:
                logger.info("✅ reference_packs.%s already exists", col_name)


async def ensure_project_generation_prompt_column(engine: AsyncEngine):
    """Ensure project-level generation prompt adjustment exists."""
    async with engine.begin() as conn:
        if not await column_exists(conn, "projects", "generation_prompt"):
            logger.info("🔧 Adding projects.generation_prompt column")
            await apply_sql(conn, [
                """ALTER TABLE projects
                ADD COLUMN generation_prompt TEXT""",
            ])
        else:
            logger.info("✅ projects.generation_prompt already exists")


async def run_auto_migrations(engine: AsyncEngine):
    try:
        await ensure_chapter_outline_columns(engine)
        await ensure_story_outline_columns(engine)
        await ensure_plot_line_link_columns(engine)
        await ensure_plot_line_columns(engine)
        await ensure_chapter_outline_scene_pov_columns(engine)  # 专业网文版字段
        await ensure_plot_cards_scene_columns(engine)  # 场景级创作循环字段
        await ensure_book_dissect_v2_columns(engine)  # 拆书 V2 字段
        await ensure_book_dissect_v31_columns(engine)  # 拆书 V3.1 字段
        await ensure_reference_pack_v32_columns(engine)  # 拆书 V3.2 synopsis 复活
        await ensure_project_generation_prompt_column(engine)
        logger.info("✅ Auto migrations finished")
    except Exception as exc:
        logger.error("❌ Auto migrations failed: %s", exc, exc_info=True)
        # Do not stop startup, but surface the error to logs
