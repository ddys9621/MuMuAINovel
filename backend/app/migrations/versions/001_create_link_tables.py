"""
创建关联表迁移脚本

创建日期: 2024-11-18
描述: 创建剧情线、章纲、剧情卡片之间的关联表
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upgrade(db: AsyncSession):
    """升级数据库：创建关联表"""
    
    # 1. 创建章纲-剧情线关联表
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS chapter_outline_plot_line_links (
            id VARCHAR(36) PRIMARY KEY,
            chapter_outline_id VARCHAR(36) NOT NULL,
            plot_line_id VARCHAR(36) NOT NULL,
            role VARCHAR(50) DEFAULT 'main',
            order_index INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_chapter_outline 
                FOREIGN KEY (chapter_outline_id) 
                REFERENCES chapter_outlines(id) 
                ON DELETE CASCADE,
            CONSTRAINT fk_plot_line_chapter 
                FOREIGN KEY (plot_line_id) 
                REFERENCES plot_lines(id) 
                ON DELETE CASCADE,
            CONSTRAINT uk_chapter_plot 
                UNIQUE (chapter_outline_id, plot_line_id)
        );
    """))
    
    # 2. 创建剧情卡片-剧情线关联表
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS plot_card_plot_line_links (
            id VARCHAR(36) PRIMARY KEY,
            plot_card_id VARCHAR(36) NOT NULL,
            plot_line_id VARCHAR(36) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_plot_card_line 
                FOREIGN KEY (plot_card_id) 
                REFERENCES plot_cards(id) 
                ON DELETE CASCADE,
            CONSTRAINT fk_plot_line_card 
                FOREIGN KEY (plot_line_id) 
                REFERENCES plot_lines(id) 
                ON DELETE CASCADE,
            CONSTRAINT uk_card_plot 
                UNIQUE (plot_card_id, plot_line_id)
        );
    """))
    
    # 3. 创建剧情卡片-章纲关联表
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS plot_card_chapter_outline_links (
            id VARCHAR(36) PRIMARY KEY,
            plot_card_id VARCHAR(36) NOT NULL,
            chapter_outline_id VARCHAR(36) NOT NULL,
            usage_type VARCHAR(50) DEFAULT 'reference',
            usage_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_plot_card_chapter 
                FOREIGN KEY (plot_card_id) 
                REFERENCES plot_cards(id) 
                ON DELETE CASCADE,
            CONSTRAINT fk_chapter_outline_card 
                FOREIGN KEY (chapter_outline_id) 
                REFERENCES chapter_outlines(id) 
                ON DELETE CASCADE,
            CONSTRAINT uk_card_chapter 
                UNIQUE (plot_card_id, chapter_outline_id)
        );
    """))
    
    await db.commit()
    print("✅ 关联表创建成功")


async def downgrade(db: AsyncSession):
    """降级数据库：删除关联表"""
    
    await db.execute(text("DROP TABLE IF EXISTS plot_card_chapter_outline_links CASCADE;"))
    await db.execute(text("DROP TABLE IF EXISTS plot_card_plot_line_links CASCADE;"))
    await db.execute(text("DROP TABLE IF EXISTS chapter_outline_plot_line_links CASCADE;"))
    
    await db.commit()
    print("✅ 关联表删除成功")
