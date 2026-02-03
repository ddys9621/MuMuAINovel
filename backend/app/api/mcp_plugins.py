"""MCP插件管理API"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.mcp_plugin import MCPPlugin
from app.schemas.mcp_plugin import (
    MCPPluginCreate,
    MCPPluginSimpleCreate,
    MCPPluginUpdate,
    MCPPluginResponse,
    MCPToolCall,
    MCPTestResult
)
import json
from app.user_manager import User
from app.mcp.registry import mcp_registry
from app.services.mcp_test_service import mcp_test_service
from app.services.mcp_tool_service import mcp_tool_service
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mcp/plugins", tags=["MCP插件管理"])


def require_login(request: Request) -> User:
    """依赖：要求用户已登录"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="需要登录")
    return request.state.user


@router.get("", response_model=List[MCPPluginResponse])
async def list_plugins(
    enabled_only: bool = Query(False, description="只返回启用的插件"),
    category: Optional[str] = Query(None, description="按分类筛选"),
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户的所有MCP插件
    """
    query = select(MCPPlugin).where(MCPPlugin.user_id == user.user_id)
    
    if enabled_only:
        query = query.where(MCPPlugin.enabled == True)
    
    if category:
        query = query.where(MCPPlugin.category == category)
    
    query = query.order_by(MCPPlugin.sort_order, MCPPlugin.created_at)
    
    result = await db.execute(query)
    plugins = result.scalars().all()
    
    logger.info(f"用户 {user.user_id} 查询插件列表，共 {len(plugins)} 个")
    return plugins


@router.post("", response_model=MCPPluginResponse)
async def create_plugin(
    data: MCPPluginCreate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的MCP插件
    """
    # 检查插件名是否已存在
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.user_id == user.user_id,
            MCPPlugin.plugin_name == data.plugin_name
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"插件名已存在: {data.plugin_name}")
    
    # 创建插件数据
    plugin_data = data.model_dump()
    
    # 如果没有提供display_name，使用plugin_name作为默认值
    if not plugin_data.get("display_name"):
        plugin_data["display_name"] = plugin_data["plugin_name"]
    
    # 创建插件
    plugin = MCPPlugin(
        user_id=user.user_id,
        **plugin_data
    )
    
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)
    
    # 如果启用，加载到注册表
    if plugin.enabled:
        success = await mcp_registry.load_plugin(plugin)
        if success:
            plugin.status = "active"
        else:
            plugin.status = "error"
            plugin.last_error = "加载失败"
        await db.commit()
        await db.refresh(plugin)
    
    logger.info(f"用户 {user.user_id} 创建插件: {plugin.plugin_name}")
    return plugin


@router.post("/simple", response_model=MCPPluginResponse)
async def create_plugin_simple(
    data: MCPPluginSimpleCreate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    通过标准MCP配置JSON创建或更新插件（简化版）
    
    接受格式：
    {
      "config_json": '{"mcpServers": {"exa": {"type": "http", "url": "...", "headers": {}}}}',
      "category": "search"
    }
    
    自动从mcpServers中提取插件名称（取第一个键）
    如果插件已存在，则更新；否则创建新插件
    """
    try:
        # 解析配置JSON
        config = json.loads(data.config_json)
        
        # 验证格式
        if "mcpServers" not in config:
            raise HTTPException(status_code=400, detail="配置JSON必须包含mcpServers字段")
        
        servers = config["mcpServers"]
        if not servers or len(servers) == 0:
            raise HTTPException(status_code=400, detail="mcpServers不能为空")
        
        # 自动提取第一个插件名称
        plugin_name = list(servers.keys())[0]
        server_config = servers[plugin_name]
        
        logger.info(f"从配置中提取插件名称: {plugin_name}")
        
        # 提取配置
        server_type = server_config.get("type", "http")
        
        if server_type not in ["http", "stdio"]:
            raise HTTPException(status_code=400, detail=f"不支持的服务器类型: {server_type}")
        
        # 检查插件名是否已存在
        result = await db.execute(
            select(MCPPlugin).where(
                MCPPlugin.user_id == user.user_id,
                MCPPlugin.plugin_name == plugin_name
            )
        )
        existing = result.scalar_one_or_none()
        
        # 构建插件数据
        plugin_data = {
            "plugin_name": plugin_name,
            "display_name": plugin_name, 
            "plugin_type": server_type,
            "enabled": data.enabled,
            "category": data.category,
            "sort_order": 0
        }
        
        if server_type == "http":
            plugin_data["server_url"] = server_config.get("url")
            plugin_data["headers"] = server_config.get("headers", {})
            
            if not plugin_data["server_url"]:
                raise HTTPException(status_code=400, detail="HTTP类型插件必须提供url字段")
        
        elif server_type == "stdio":
            plugin_data["command"] = server_config.get("command")
            plugin_data["args"] = server_config.get("args", [])
            plugin_data["env"] = server_config.get("env", {})
            
            if not plugin_data["command"]:
                raise HTTPException(status_code=400, detail="Stdio类型插件必须提供command字段")
        
        if existing:
            # 更新现有插件
            logger.info(f"插件 {plugin_name} 已存在，执行更新操作")
            
            # 先卸载旧插件
            if existing.enabled:
                await mcp_registry.unload_plugin(user.user_id, existing.plugin_name)
            
            # 更新字段
            for key, value in plugin_data.items():
                setattr(existing, key, value)
            
            plugin = existing
            await db.commit()
            await db.refresh(plugin)
            
            # 如果启用，重新加载
            if plugin.enabled:
                success = await mcp_registry.load_plugin(plugin)
                if success:
                    plugin.status = "active"
                    plugin.last_error = None
                else:
                    plugin.status = "error"
                    plugin.last_error = "加载失败"
                await db.commit()
                await db.refresh(plugin)
            
            logger.info(f"用户 {user.user_id} 更新插件: {plugin_name}")
        else:
            # 创建新插件
            plugin = MCPPlugin(
                user_id=user.user_id,
                **plugin_data
            )
            
            db.add(plugin)
            await db.commit()
            await db.refresh(plugin)
            
            # 如果启用，加载到注册表
            if plugin.enabled:
                success = await mcp_registry.load_plugin(plugin)
                if success:
                    plugin.status = "active"
                else:
                    plugin.status = "error"
                    plugin.last_error = "加载失败"
                await db.commit()
                await db.refresh(plugin)
            
            logger.info(f"用户 {user.user_id} 通过简化配置创建插件: {plugin_name}")
        
        return plugin
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"配置JSON格式错误: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建插件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建插件失败: {str(e)}")


@router.get("/{plugin_id}", response_model=MCPPluginResponse)
async def get_plugin(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    获取插件详情
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    return plugin


@router.put("/{plugin_id}", response_model=MCPPluginResponse)
async def update_plugin(
    plugin_id: str,
    data: MCPPluginUpdate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    更新插件配置
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plugin, key, value)
    
    await db.commit()
    await db.refresh(plugin)
    
    # 如果插件已启用，重新加载
    if plugin.enabled:
        await mcp_registry.reload_plugin(plugin)
    
    logger.info(f"用户 {user.user_id} 更新插件: {plugin.plugin_name}")
    return plugin


@router.delete("/{plugin_id}")
async def delete_plugin(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    删除插件
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    # 从注册表卸载
    await mcp_registry.unload_plugin(user.user_id, plugin.plugin_name)
    
    # 删除数据库记录
    await db.delete(plugin)
    await db.commit()
    
    logger.info(f"用户 {user.user_id} 删除插件: {plugin.plugin_name}")
    return {"message": "插件已删除", "plugin_name": plugin.plugin_name}


@router.post("/{plugin_id}/toggle", response_model=MCPPluginResponse)
async def toggle_plugin(
    plugin_id: str,
    enabled: bool = Query(..., description="启用或禁用"),
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    启用或禁用插件
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    plugin.enabled = enabled
    
    if enabled:
        # 启用：加载到注册表
        success = await mcp_registry.load_plugin(plugin)
        if success:
            plugin.status = "active"
            plugin.last_error = None
        else:
            plugin.status = "error"
            plugin.last_error = "加载失败"
    else:
        # 禁用：从注册表卸载
        await mcp_registry.unload_plugin(user.user_id, plugin.plugin_name)
        plugin.status = "inactive"
    
    await db.commit()
    await db.refresh(plugin)
    
    action = "启用" if enabled else "禁用"
    logger.info(f"用户 {user.user_id} {action}插件: {plugin.plugin_name}")
    return plugin


@router.post("/{plugin_id}/test", response_model=MCPTestResult)
async def test_plugin(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    测试插件连接并调用工具验证功能
    
    使用新的MCPTestService进行测试
    """
    
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    if not plugin.enabled:
        return MCPTestResult(
            success=False,
            message="插件未启用",
            error="请先启用插件",
            suggestions=["点击开关按钮启用插件"]
        )
    
    # 使用新的测试服务
    try:
        test_result = await mcp_test_service.test_plugin_with_ai(plugin, user, db)
        
        # 更新插件状态
        if test_result.success:
            plugin.status = "active"
            plugin.last_error = None
        else:
            plugin.status = "error"
            plugin.last_error = test_result.error
        
        plugin.last_test_at = datetime.now()
        await db.commit()
        
        return test_result
        
    except Exception as e:
        logger.error(f"测试插件失败: {plugin.plugin_name}, 错误: {e}")
        plugin.status = "error"
        plugin.last_error = str(e)
        plugin.last_test_at = datetime.now()
        await db.commit()
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


async def _ensure_plugin_loaded(
    plugin: MCPPlugin,
    user_id: str
) -> bool:
    """
    确保插件已加载（共享逻辑）
    
    Args:
        plugin: 插件对象
        user_id: 用户ID
        
    Returns:
        是否加载成功
        
    Raises:
        HTTPException: 加载失败
    """
    if not mcp_registry.get_client(user_id, plugin.plugin_name):
        logger.info(f"插件 {plugin.plugin_name} 未加载，自动加载中...")
        success = await mcp_registry.load_plugin(plugin)
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"插件加载失败: {plugin.plugin_name}"
            )
    return True


@router.get("/metrics")
async def get_metrics(
    tool_name: Optional[str] = Query(None, description="工具名称（可选，获取特定工具的指标）"),
    user: User = Depends(require_login)
):
    """
    获取MCP工具调用指标
    
    Query参数:
        - tool_name: 可选，指定工具名称获取特定工具的指标
        
    Returns:
        工具调用指标字典，包含：
        - total_calls: 总调用次数
        - success_calls: 成功调用次数
        - failed_calls: 失败调用次数
        - success_rate: 成功率
        - avg_duration_ms: 平均耗时（毫秒）
        - last_call_time: 最后调用时间
    """
    metrics = mcp_tool_service.get_metrics(tool_name)
    
    return {
        "metrics": metrics,
        "tool_name": tool_name,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/cache/stats")
async def get_cache_stats(
    user: User = Depends(require_login)
):
    """
    获取工具缓存统计信息
    
    Returns:
        缓存统计信息，包含：
        - total_entries: 缓存条目总数
        - total_hits: 缓存总命中次数
        - cache_ttl_minutes: 缓存TTL（分钟）
        - entries: 各缓存条目详情
    """
    stats = mcp_tool_service.get_cache_stats()
    
    return {
        "cache_stats": stats,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/cache/clear")
async def clear_cache(
    user_id: Optional[str] = Query(None, description="用户ID（可选）"),
    plugin_name: Optional[str] = Query(None, description="插件名称（可选）"),
    user: User = Depends(require_login)
):
    """
    清理工具缓存
    
    Query参数:
        - user_id: 可选，清理特定用户的缓存
        - plugin_name: 可选，清理特定插件的缓存
        
    说明:
        - 不提供任何参数：清理所有缓存
        - 只提供user_id：清理该用户的所有缓存
        - 提供user_id和plugin_name：清理特定插件的缓存
    """
    # 非管理员只能清理自己的缓存
    if user_id and user_id != user.user_id:
        raise HTTPException(status_code=403, detail="无权清理其他用户的缓存")
    
    # 如果没有指定user_id，使用当前用户
    target_user_id = user_id or user.user_id
    
    mcp_tool_service.clear_cache(target_user_id, plugin_name)
    
    message = "已清理"
    if plugin_name:
        message += f"插件 {plugin_name} 的缓存"
    elif target_user_id:
        message += f"用户 {target_user_id} 的所有缓存"
    else:
        message += "所有缓存"
    
    logger.info(f"用户 {user.user_id} {message}")
    
    return {
        "success": True,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/{plugin_id}/tools")
async def get_plugin_tools(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    获取插件提供的工具列表
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    if not plugin.enabled:
        raise HTTPException(status_code=400, detail="插件未启用")
    
    try:
        # 确保插件已加载
        await _ensure_plugin_loaded(plugin, user.user_id)
        
        tools = await mcp_registry.get_plugin_tools(user.user_id, plugin.plugin_name)
        
        # 更新缓存
        plugin.tools = tools
        await db.commit()
        
        return {
            "plugin_name": plugin.plugin_name,
            "tools": tools,
            "count": len(tools)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工具列表失败: {plugin.plugin_name}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"获取工具列表失败: {str(e)}")


@router.post("/call")
async def call_mcp_tool(
    data: MCPToolCall,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    调用MCP工具
    """
    # 获取插件
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == data.plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    
    if not plugin.enabled:
        raise HTTPException(status_code=400, detail="插件未启用")
    
    try:
        # 确保插件已加载
        await _ensure_plugin_loaded(plugin, user.user_id)
        
        # 调用工具
        result = await mcp_registry.call_tool(
            user.user_id,
            plugin.plugin_name,
            data.tool_name,
            data.arguments
        )
        
        return {
            "success": True,
            "plugin_name": plugin.plugin_name,
            "tool_name": data.tool_name,
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"调用工具失败: {plugin.plugin_name}.{data.tool_name}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"工具调用失败: {str(e)}")