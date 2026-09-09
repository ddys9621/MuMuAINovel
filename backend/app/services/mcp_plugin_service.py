"""MCP插件落库服务 - 「快速添加」与「商城一键安装」共用的创建/更新逻辑"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import get_logger
from app.mcp.registry import mcp_registry
from app.models.mcp_plugin import MCPPlugin

logger = get_logger(__name__)


async def upsert_plugin(
    db: AsyncSession,
    user_id: str,
    plugin_data: Dict[str, Any],
    *,
    category: str,
    enabled: bool,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
) -> MCPPlugin:
    """
    按 (user_id, plugin_name) 创建或更新插件，并在启用时（重新）加载到注册表、写回 status。

    Args:
        db: 数据库会话
        user_id: 用户ID
        plugin_data: parse_server_config() 输出的字段字典（含 plugin_name / plugin_type / server_url / config 等）
        category: 插件分类
        enabled: 是否启用
        display_name: 显示名（缺省用 plugin_data 里的 display_name）
        description: 插件描述（None 时不覆盖已有描述）

    Returns:
        已提交并刷新的插件对象
    """
    plugin_name = plugin_data["plugin_name"]
    result = await db.execute(
        select(MCPPlugin).where(MCPPlugin.user_id == user_id, MCPPlugin.plugin_name == plugin_name)
    )
    existing = result.scalar_one_or_none()

    values = {**plugin_data, "category": category, "enabled": enabled}
    if display_name:
        values["display_name"] = display_name
    if description is not None:
        values["description"] = description

    if existing:
        logger.info(f"插件 {plugin_name} 已存在，执行更新操作")
        if existing.enabled:
            await mcp_registry.unload_plugin(user_id, existing.plugin_name)
        for key, value in values.items():
            setattr(existing, key, value)
        plugin = existing
    else:
        plugin = MCPPlugin(user_id=user_id, **values)
        db.add(plugin)

    await db.commit()
    await db.refresh(plugin)

    if plugin.enabled:
        success = await mcp_registry.load_plugin(plugin)
        plugin.status = "active" if success else "error"
        plugin.last_error = None if success else "加载失败"
        await db.commit()
        await db.refresh(plugin)

    return plugin
