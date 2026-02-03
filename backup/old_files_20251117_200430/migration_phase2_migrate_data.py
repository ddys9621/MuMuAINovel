"""
Phase 2: 数据迁移脚本
将现有数据迁移到新的多层级结构
"""
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import uuid
from datetime import datetime
import json

# 导入配置
from app.config import settings

async def migrate_data():
    """执行数据迁移"""
    # 使用异步引擎
    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = AsyncSessionLocal()
    
    try:
        print("=" * 60)
        print("开始数据迁移...")
        print("=" * 60)
        
        # Step 1: 为每个项目创建默认故事大纲
        print("\n[Step 1] 创建默认故事大纲...")
        migrate_story_outlines(session)
        
        # Step 2: 迁移 plot_lines 的 outline_id 到 story_outline_id
        print("\n[Step 2] 迁移剧情线关联...")
        migrate_plot_line_associations(session)
        
        # Step 3: 迁移 chapter_outlines 的 plot_line_id 到关联表
        print("\n[Step 3] 迁移章纲-剧情线关联...")
        migrate_chapter_outline_plot_line_links(session)
        
        # Step 4: 迁移 plot_cards 的关联关系
        print("\n[Step 4] 迁移素材关联...")
        migrate_plot_card_associations(session)
        
        # Step 5: 数据验证
        print("\n[Step 5] 验证数据完整性...")
        validate_migration(session)
        
        session.commit()
        print("\n" + "=" * 60)
        print("数据迁移完成！")
        print("=" * 60)
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ 迁移失败: {str(e)}")
        raise
    finally:
        session.close()


def migrate_story_outlines(session):
    """为每个项目创建默认故事大纲"""
    # 获取所有项目
    projects = session.execute(text("SELECT id, title FROM projects")).fetchall()
    
    for project in projects:
        project_id = project[0]
        project_title = project[1]
        
        # 检查是否已有大纲
        existing = session.execute(
            text("SELECT COUNT(*) FROM outlines WHERE project_id = :pid"),
            {"pid": project_id}
        ).scalar()
        
        if existing > 0:
            # 将现有 outlines 转换为 story_outlines
            outlines = session.execute(
                text("""
                    SELECT id, title, content, structure, order_index, created_at, updated_at 
                    FROM outlines 
                    WHERE project_id = :pid
                    ORDER BY created_at
                """),
                {"pid": project_id}
            ).fetchall()
            
            for idx, outline in enumerate(outlines):
                story_outline_id = str(uuid.uuid4())
                session.execute(
                    text("""
                        INSERT INTO story_outlines 
                        (id, project_id, title, content, structure, version, is_active, order_index, created_at, updated_at)
                        VALUES 
                        (:id, :pid, :title, :content, :structure, :version, :is_active, :order_idx, :created, :updated)
                    """),
                    {
                        "id": story_outline_id,
                        "pid": project_id,
                        "title": outline[1] or f"故事大纲 {idx + 1}",
                        "content": outline[2],
                        "structure": outline[3],
                        "version": idx + 1,
                        "is_active": idx == len(outlines) - 1,  # 最后一个为激活版本
                        "order_idx": outline[4],
                        "created": outline[5],
                        "updated": outline[6]
                    }
                )
                print(f"  ✓ 项目 {project_title}: 创建故事大纲 v{idx + 1}")
        else:
            # 创建默认大纲
            story_outline_id = str(uuid.uuid4())
            session.execute(
                text("""
                    INSERT INTO story_outlines 
                    (id, project_id, title, content, version, is_active, created_at, updated_at)
                    VALUES 
                    (:id, :pid, :title, :content, 1, TRUE, NOW(), NOW())
                """),
                {
                    "id": story_outline_id,
                    "pid": project_id,
                    "title": f"{project_title} - 默认大纲",
                    "content": "系统自动创建的默认大纲"
                }
            )
            print(f"  ✓ 项目 {project_title}: 创建默认故事大纲")


def migrate_plot_line_associations(session):
    """迁移剧情线的 outline_id 到 story_outline_id"""
    # 获取所有剧情线
    plot_lines = session.execute(
        text("SELECT id, project_id, outline_id FROM plot_lines WHERE outline_id IS NOT NULL")
    ).fetchall()
    
    for plot_line in plot_lines:
        plot_line_id, project_id, outline_id = plot_line
        
        # 查找对应的 story_outline
        story_outline = session.execute(
            text("""
                SELECT id FROM story_outlines 
                WHERE project_id = :pid AND is_active = TRUE
                LIMIT 1
            """),
            {"pid": project_id}
        ).fetchone()
        
        if story_outline:
            story_outline_id = story_outline[0]
            session.execute(
                text("UPDATE plot_lines SET story_outline_id = :soid WHERE id = :plid"),
                {"soid": story_outline_id, "plid": plot_line_id}
            )
            print(f"  ✓ 剧情线 {plot_line_id[:8]}: 关联到故事大纲")
        else:
            print(f"  ⚠ 剧情线 {plot_line_id[:8]}: 未找到对应故事大纲")


def migrate_chapter_outline_plot_line_links(session):
    """迁移章纲的 plot_line_id 到关联表"""
    # 获取所有章纲
    chapter_outlines = session.execute(
        text("SELECT id, plot_line_id FROM chapter_outlines WHERE plot_line_id IS NOT NULL")
    ).fetchall()
    
    for chapter_outline in chapter_outlines:
        chapter_outline_id, plot_line_id = chapter_outline
        
        # 创建关联记录
        link_id = str(uuid.uuid4())
        session.execute(
            text("""
                INSERT INTO chapter_outline_plot_line_links 
                (id, chapter_outline_id, plot_line_id, role, order_index, created_at)
                VALUES 
                (:id, :coid, :plid, 'main', 1, NOW())
                ON DUPLICATE KEY UPDATE order_index = order_index
            """),
            {
                "id": link_id,
                "coid": chapter_outline_id,
                "plid": plot_line_id
            }
        )
        print(f"  ✓ 章纲 {chapter_outline_id[:8]}: 关联剧情线 {plot_line_id[:8]}")


def migrate_plot_card_associations(session):
    """迁移素材的关联关系"""
    # 1. 迁移 plot_cards.outline_id 到 plot_card_plot_line_links
    plot_cards_with_outline = session.execute(
        text("""
            SELECT pc.id, pc.outline_id, pc.project_id
            FROM plot_cards pc
            WHERE pc.outline_id IS NOT NULL
        """)
    ).fetchall()
    
    for plot_card in plot_cards_with_outline:
        plot_card_id, outline_id, project_id = plot_card
        
        # 查找该 outline 对应的剧情线
        plot_lines = session.execute(
            text("""
                SELECT id FROM plot_lines 
                WHERE project_id = :pid
                LIMIT 1
            """),
            {"pid": project_id}
        ).fetchall()
        
        for plot_line in plot_lines:
            plot_line_id = plot_line[0]
            link_id = str(uuid.uuid4())
            session.execute(
                text("""
                    INSERT INTO plot_card_plot_line_links 
                    (id, plot_card_id, plot_line_id, created_at)
                    VALUES 
                    (:id, :pcid, :plid, NOW())
                    ON DUPLICATE KEY UPDATE created_at = created_at
                """),
                {
                    "id": link_id,
                    "pcid": plot_card_id,
                    "plid": plot_line_id
                }
            )
            print(f"  ✓ 素材 {plot_card_id[:8]}: 关联剧情线 {plot_line_id[:8]}")
    
    # 2. 迁移 plot_cards.chapter_outline_id 到 plot_card_chapter_outline_links
    plot_cards_with_chapter = session.execute(
        text("""
            SELECT id, chapter_outline_id
            FROM plot_cards
            WHERE chapter_outline_id IS NOT NULL
        """)
    ).fetchall()
    
    for plot_card in plot_cards_with_chapter:
        plot_card_id, chapter_outline_id = plot_card
        
        link_id = str(uuid.uuid4())
        session.execute(
            text("""
                INSERT INTO plot_card_chapter_outline_links 
                (id, plot_card_id, chapter_outline_id, usage_type, created_at, updated_at)
                VALUES 
                (:id, :pcid, :coid, 'reference', NOW(), NOW())
                ON DUPLICATE KEY UPDATE updated_at = NOW()
            """),
            {
                "id": link_id,
                "pcid": plot_card_id,
                "coid": chapter_outline_id
            }
        )
        print(f"  ✓ 素材 {plot_card_id[:8]}: 关联章纲 {chapter_outline_id[:8]}")


def validate_migration(session):
    """验证数据完整性"""
    # 验证 story_outlines
    story_outline_count = session.execute(
        text("SELECT COUNT(*) FROM story_outlines")
    ).scalar()
    print(f"  ✓ 故事大纲总数: {story_outline_count}")
    
    # 验证 plot_lines 关联
    plot_line_linked = session.execute(
        text("SELECT COUNT(*) FROM plot_lines WHERE story_outline_id IS NOT NULL")
    ).scalar()
    print(f"  ✓ 已关联故事大纲的剧情线: {plot_line_linked}")
    
    # 验证章纲-剧情线关联
    chapter_plot_links = session.execute(
        text("SELECT COUNT(*) FROM chapter_outline_plot_line_links")
    ).scalar()
    print(f"  ✓ 章纲-剧情线关联数: {chapter_plot_links}")
    
    # 验证素材关联
    card_plot_links = session.execute(
        text("SELECT COUNT(*) FROM plot_card_plot_line_links")
    ).scalar()
    card_chapter_links = session.execute(
        text("SELECT COUNT(*) FROM plot_card_chapter_outline_links")
    ).scalar()
    print(f"  ✓ 素材-剧情线关联数: {card_plot_links}")
    print(f"  ✓ 素材-章纲关联数: {card_chapter_links}")


if __name__ == "__main__":
    migrate_data()
