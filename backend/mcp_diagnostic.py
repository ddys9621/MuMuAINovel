"""MCP 调用链路诊断脚本

用于诊断 MCP 工具未被调用的问题
"""
import asyncio
import sys
from sqlalchemy import select

# 先设置事件循环，避免 MCP registry 初始化错误
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from app.database import get_db
from app.models import Project
from app.services.ai_service import AIService
from app.logger import get_logger

logger = get_logger(__name__)


async def diagnose_mcp_chain():
    """诊断 MCP 调用链路"""
    
    print("\n" + "="*60)
    print("MCP 调用链路诊断")
    print("="*60 + "\n")
    
    # 1. 检查数据库连接
    print("1. 检查数据库连接...")
    try:
        # 直接使用数据库引擎，不需要 Request 对象
        from app.database import get_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        
        # 使用默认用户ID（PostgreSQL 共享模式）
        engine = await get_engine("diagnostic_user")
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as db:
            # 获取第一个项目
            result = await db.execute(select(Project).limit(1))
            project = result.scalar_one_or_none()
            
            if not project:
                print("   ❌ 数据库中没有项目")
                return
            
            print(f"   ✅ 找到项目: {project.title} (ID: {project.id})")
            print(f"   - user_id: {project.user_id}")
            
            # 2. 使用项目的 user_id
            print("\n2. 检查用户ID...")
            if not project.user_id:
                print("   ❌ 项目没有关联用户")
                return
            
            user_id = project.user_id
            print(f"   ✅ 用户ID: {user_id}")
            
            # 3. 检查 MCP 工具
            print("\n3. 检查 MCP 工具...")
            try:
                # 延迟导入，确保事件循环已设置
                from app.services.mcp_tool_service import mcp_tool_service
                
                tools = await mcp_tool_service.get_user_enabled_tools(
                    user_id=user_id,
                    db_session=db
                )
                
                if not tools:
                    print("   ⚠️  用户没有启用任何 MCP 工具")
                    print("   提示: 请在设置中启用 MCP 插件")
                else:
                    print(f"   ✅ 找到 {len(tools)} 个可用工具:")
                    for tool in tools[:5]:  # 只显示前5个
                        print(f"      - {tool.get('function', {}).get('name', 'unknown')}")
            except Exception as e:
                print(f"   ❌ 获取 MCP 工具失败: {e}")
                import traceback
                traceback.print_exc()
            
            # 4. 测试 AI 服务
            print("\n4. 测试 AI 服务...")
            try:
                ai_service = AIService()
                print(f"   ✅ AI 服务初始化成功")
                print(f"   - Provider: {ai_service.api_provider}")
                print(f"   - Model: {ai_service.default_model}")
                
                # 5. 测试 MCP 调用
                print("\n5. 测试 MCP 调用...")
                test_prompt = "请简单介绍一下你自己"
                
                print(f"   测试提示词: {test_prompt}")
                print(f"   enable_mcp: True")
                print(f"   tool_choice: auto")
                
                result = await ai_service.generate_text_with_mcp(
                    prompt=test_prompt,
                    user_id=user_id,
                    db_session=db,
                    enable_mcp=True,
                    tool_choice="auto",
                    context="诊断测试"
                )
                
                print(f"\n   结果:")
                print(f"   - 内容长度: {len(result.get('content', ''))} 字符")
                print(f"   - 工具调用次数: {result.get('tool_calls_made', 0)}")
                print(f"   - 使用的工具: {result.get('tools_used', [])}")
                print(f"   - MCP 增强: {result.get('mcp_enhanced', False)}")
                print(f"   - 完成原因: {result.get('finish_reason', 'unknown')}")
                
                if result.get('tool_calls_made', 0) > 0:
                    print(f"\n   ✅ MCP 工具调用成功!")
                else:
                    print(f"\n   ⚠️  MCP 工具未被调用")
                    print(f"   可能原因:")
                    print(f"   1. AI 判断不需要使用工具")
                    print(f"   2. 工具列表为空")
                    print(f"   3. tool_choice 设置不当")
                
            except Exception as e:
                print(f"   ❌ AI 服务测试失败: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        print(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("诊断完成")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(diagnose_mcp_chain())
