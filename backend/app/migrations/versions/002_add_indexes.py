"""
添加索引迁移脚本

创建日期: 2024-11-18
描述: 为关联表添加索引以提升查询性能
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upgrade(db: AsyncSession):
    """升级数据库：添加索引"""
    
    # 章纲-剧情线关联表索引
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chapter_outline_links_chapter 
        ON chapter_outline_plot_line_links(chapter_outline_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chapter_outline_links_plot 
        ON chapter_outline_plot_line_links(plot_line_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chapter_outline_links_role 
        ON chapter_outline_plot_line_links(role);
    """))
    
    # 剧情卡片-剧情线关联表索引
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_card_line_links_card 
        ON plot_card_plot_line_links(plot_card_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_card_line_links_plot 
        ON plot_card_plot_line_links(plot_line_id);
    """))
    
    # 剧情卡片-章纲关联表索引
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_card_chapter_links_card 
        ON plot_card_chapter_outline_links(plot_card_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_card_chapter_links_chapter 
        ON plot_card_chapter_outline_links(chapter_outline_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_card_chapter_links_usage 
        ON plot_card_chapter_outline_links(usage_type);
    """))
    
    # 主表索引优化
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_lines_project 
        ON plot_lines(project_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chapter_outlines_project 
        ON chapter_outlines(project_id);
    """))
    
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_plot_cards_project 
        ON plot_cards(project_id);
    """))
    
    await db.commit()
    print("✅ 索引创建成功")


async def downgrade(db: AsyncSession):
    """降级数据库：删除索引"""
    
    # 删除关联表索引
    await db.execute(text("DROP INDEX IF EXISTS idx_chapter_outline_links_chapter;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_chapter_outline_links_plot;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_chapter_outline_links_role;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_card_line_links_card;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_card_line_links_plot;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_card_chapter_links_card;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_card_chapter_links_chapter;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_card_chapter_links_usage;"))
    
    # 删除主表索引
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_lines_project;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_chapter_outlines_project;"))
    await db.execute(text("DROP INDEX IF EXISTS idx_plot_cards_project;"))
    
    await db.commit()
    print("✅ 索引删除成功")
