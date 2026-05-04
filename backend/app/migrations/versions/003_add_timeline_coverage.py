"""
添加 timeline_coverage 字段迁移脚本

创建日期: 2025-11-21
描述: 为 chapter_outline_plot_line_links 表添加 timeline_coverage 字段，用于记录章节对剧情线节点的覆盖情况
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upgrade(db: AsyncSession):
    """升级数据库：添加 timeline_coverage 字段"""
    
    # 为 chapter_outline_plot_line_links 表添加 timeline_coverage 字段
    await db.execute(text("""
        ALTER TABLE chapter_outline_plot_line_links 
        ADD COLUMN IF NOT EXISTS timeline_coverage TEXT;
    """))
    
    # 添加字段注释（仅 PostgreSQL 支持，SQLite 静默跳过）
    try:
        await db.execute(text("""
            COMMENT ON COLUMN chapter_outline_plot_line_links.timeline_coverage 
            IS '时间线覆盖数据，JSON格式：记录该章节对该剧情线各节点的覆盖情况';
        """))
    except Exception as e:
        # SQLite 不支持 COMMENT，忽略错误
        print(f"⚠️  添加字段注释失败（可能是 SQLite 数据库）: {e}")
    
    await db.commit()
    print("✅ timeline_coverage 字段添加成功")


async def downgrade(db: AsyncSession):
    """降级数据库：删除 timeline_coverage 字段"""
    
    await db.execute(text("""
        ALTER TABLE chapter_outline_plot_line_links 
        DROP COLUMN IF EXISTS timeline_coverage;
    """))
    
    await db.commit()
    print("✅ timeline_coverage 字段删除成功")

