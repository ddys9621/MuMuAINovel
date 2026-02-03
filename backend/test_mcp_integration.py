"""MCP 集成测试脚本

测试 MCP 工具在剧情生成中的集成
"""
import asyncio
import sys
from sqlalchemy import select
from app.database import get_db
from app.models import Project, User, StoryOutline
from app.services.ai_service import AIService
from app.services.plot_generation_service import PlotGenerationService
from app.logger import get_logger

logger = get_logger(__name__)


async def test_plot_card_generation_with_mcp():
    """测试剧情卡片生成（启用 MCP）"""
    
    print("\n" + "="*60)
    print("测试剧情卡片生成（MCP 增强）")
    print("="*60 + "\n")
    
    async for db in get_db():
        try:
            # 1. 获取测试数据
            print("1. 准备测试数据...")
            
            # 获取第一个项目
            project_result = await db.execute(select(Project).limit(1))
            project = project_result.scalar_one_or_none()
            
            if not project:
                print("   ❌ 没有找到项目")
                return
            
            print(f"   ✅ 项目: {project.title} (ID: {project.id})")
            
            # 获取用户
            if not project.user_id:
                print("   ❌ 项目没有关联用户")
                return
            
            user_result = await db.execute(select(User).where(User.id == project.user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                print(f"   ❌ 用户不存在: {project.user_id}")
                return
            
            print(f"   ✅ 用户: {user.username} (ID: {user.id})")
            
            # 获取大纲
            outline_result = await db.execute(
                select(StoryOutline)
                .where(StoryOutline.project_id == project.id)
                .limit(1)
            )
            outline = outline_result.scalar_one_or_none()
            
            if not outline:
                print("   ❌ 项目没有大纲")
                return
            
            print(f"   ✅ 大纲: {outline.title} (ID: {outline.id})")
            
            # 2. 测试基础模式（不启用 MCP）
            print("\n2. 测试基础模式（enable_mcp=False）...")
            
            ai_service = AIService()
            plot_service = PlotGenerationService(ai_service)
            
            try:
                cards_basic = await plot_service.generate_plot_cards(
                    db=db,
                    project_id=project.id,
                    outline_id=outline.id,
                    card_type="plot",
                    count=1,
                    enable_mcp=False,
                    user_id=user.id
                )
                
                print(f"   ✅ 基础模式生成成功: {len(cards_basic)} 个卡片")
                if cards_basic:
                    print(f"   - 标题: {cards_basic[0].title}")
                    print(f"   - 内容长度: {len(cards_basic[0].content)} 字符")
                
            except Exception as e:
                print(f"   ❌ 基础模式生成失败: {e}")
                import traceback
                traceback.print_exc()
            
            # 3. 测试 MCP 增强模式
            print("\n3. 测试 MCP 增强模式（enable_mcp=True）...")
            
            try:
                cards_mcp = await plot_service.generate_plot_cards(
                    db=db,
                    project_id=project.id,
                    outline_id=outline.id,
                    card_type="plot",
                    count=1,
                    enable_mcp=True,
                    selected_plugins=None,  # 使用所有可用工具
                    user_id=user.id
                )
                
                print(f"   ✅ MCP 模式生成成功: {len(cards_mcp)} 个卡片")
                if cards_mcp:
                    print(f"   - 标题: {cards_mcp[0].title}")
                    print(f"   - 内容长度: {len(cards_mcp[0].content)} 字符")
                
                # 比较内容长度
                if cards_basic and cards_mcp:
                    basic_len = len(cards_basic[0].content)
                    mcp_len = len(cards_mcp[0].content)
                    
                    print(f"\n   📊 内容对比:")
                    print(f"   - 基础模式: {basic_len} 字符")
                    print(f"   - MCP 模式: {mcp_len} 字符")
                    print(f"   - 差异: {mcp_len - basic_len:+d} 字符 ({(mcp_len/basic_len-1)*100:+.1f}%)")
                
            except Exception as e:
                print(f"   ❌ MCP 模式生成失败: {e}")
                import traceback
                traceback.print_exc()
            
            # 4. 测试指定插件
            print("\n4. 测试指定插件（selected_plugins=['exa']）...")
            
            try:
                cards_exa = await plot_service.generate_plot_cards(
                    db=db,
                    project_id=project.id,
                    outline_id=outline.id,
                    card_type="plot",
                    count=1,
                    enable_mcp=True,
                    selected_plugins=["exa"],
                    user_id=user.id
                )
                
                print(f"   ✅ 指定插件生成成功: {len(cards_exa)} 个卡片")
                if cards_exa:
                    print(f"   - 标题: {cards_exa[0].title}")
                    print(f"   - 内容长度: {len(cards_exa[0].content)} 字符")
                
            except Exception as e:
                print(f"   ❌ 指定插件生成失败: {e}")
                import traceback
                traceback.print_exc()
            
            print("\n" + "="*60)
            print("测试完成")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 回滚测试数据
            await db.rollback()
            print("\n已回滚测试数据")
        
        break


async def test_chapter_outline_generation_with_mcp():
    """测试章纲生成（启用 MCP）"""
    
    print("\n" + "="*60)
    print("测试章纲生成（MCP 增强）")
    print("="*60 + "\n")
    
    async for db in get_db():
        try:
            # 获取测试数据
            project_result = await db.execute(select(Project).limit(1))
            project = project_result.scalar_one_or_none()
            
            if not project or not project.user_id:
                print("   ❌ 没有找到有效的项目")
                return
            
            print(f"   ✅ 项目: {project.title}")
            
            # 测试章纲生成
            ai_service = AIService()
            plot_service = PlotGenerationService(ai_service)
            
            print("\n测试 MCP 增强章纲生成...")
            
            try:
                outlines = await plot_service.generate_chapter_outlines(
                    db=db,
                    project_id=project.id,
                    start_chapter=1,
                    chapter_count=2,
                    target_word_count=3000,
                    enable_mcp=True,
                    user_id=project.user_id
                )
                
                print(f"   ✅ 生成成功: {len(outlines)} 个章纲")
                for outline in outlines:
                    print(f"   - 第{outline.chapter_number}章: {outline.title}")
                    print(f"     摘要长度: {len(outline.summary or '')} 字符")
                
            except Exception as e:
                print(f"   ❌ 生成失败: {e}")
                import traceback
                traceback.print_exc()
            
        finally:
            await db.rollback()
            print("\n已回滚测试数据")
        
        break


if __name__ == "__main__":
    print("\n选择测试:")
    print("1. 剧情卡片生成")
    print("2. 章纲生成")
    print("3. 全部测试")
    
    choice = input("\n请输入选项 (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_plot_card_generation_with_mcp())
    elif choice == "2":
        asyncio.run(test_chapter_outline_generation_with_mcp())
    elif choice == "3":
        asyncio.run(test_plot_card_generation_with_mcp())
        asyncio.run(test_chapter_outline_generation_with_mcp())
    else:
        print("无效的选项")
