"""
添加 estimated_chapters 字段迁移脚本

创建日期: 2025-11-21
描述: 为 plot_lines 表添加 estimated_chapters 字段，用于记录完成该剧情线预计需要的章节数量
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upgrade(db: AsyncSession):
    """升级数据库：添加 estimated_chapters 字段"""
    
    # 为 plot_lines 表添加 estimated_chapters 字段
    await db.execute(text("""
        ALTER TABLE plot_lines 
        ADD COLUMN IF NOT EXISTS estimated_chapters INTEGER;
    """))
    
    # 添加字段注释（仅 PostgreSQL 支持，SQLite 静默跳过）
    try:
        await db.execute(text("""
            COMMENT ON COLUMN plot_lines.estimated_chapters 
            IS '预计章节数：完成这条剧情线预计需要的章节数量';
        """))
    except Exception as e:
        # SQLite 不支持 COMMENT，忽略错误
        print(f"⚠️  添加字段注释失败（可能是 SQLite 数据库）: {e}")
    
    # 为已有数据设置默认值（基于 line_type）
    print("📊 为已有剧情线设置默认预计章节数...")
    
    # 主线剧情线默认 40 章
    result = await db.execute(text("""
        UPDATE plot_lines 
        SET estimated_chapters = 40
        WHERE line_type = 'main' AND estimated_chapters IS NULL;
    """))
    main_count = result.rowcount
    
    # 支线剧情线默认 15 章
    result = await db.execute(text("""
        UPDATE plot_lines 
        SET estimated_chapters = 15
        WHERE line_type = 'sub' AND estimated_chapters IS NULL;
    """))
    sub_count = result.rowcount
    
    # 其他类型默认 8 章
    result = await db.execute(text("""
        UPDATE plot_lines 
        SET estimated_chapters = 8
        WHERE estimated_chapters IS NULL;
    """))
    other_count = result.rowcount
    
    await db.commit()
    
    print(f"✅ estimated_chapters 字段添加成功")
    print(f"   - 主线剧情线: {main_count} 条设置为 40 章")
    print(f"   - 支线剧情线: {sub_count} 条设置为 15 章")
    print(f"   - 其他剧情线: {other_count} 条设置为 8 章")


async def downgrade(db: AsyncSession):
    """降级数据库：删除 estimated_chapters 字段"""
    
    await db.execute(text("""
        ALTER TABLE plot_lines 
        DROP COLUMN IF EXISTS estimated_chapters;
    """))
    
    await db.commit()
    print("✅ estimated_chapters 字段删除成功")

