"""MCP 商城 API - 内置精选目录浏览 + 一键安装为当前用户的插件"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logger import get_logger
from app.mcp.marketplace import CATEGORIES, MarketplaceInputError, get_item, load_catalog, render_server_config
from app.mcp.server_config import parse_server_config
from app.models.mcp_plugin import MCPPlugin
from app.schemas.mcp_plugin import (
    MCPMarketplaceInstallRequest,
    MCPMarketplaceItemResponse,
    MCPMarketplaceListResponse,
    MCPPluginResponse,
)
from app.services.mcp_plugin_service import upsert_plugin
from app.user_manager import User
from app.api.deps import require_login

logger = get_logger(__name__)

router = APIRouter(prefix="/mcp/marketplace", tags=["MCP商城"])


@router.get("", response_model=MCPMarketplaceListResponse)
async def list_marketplace(
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """
    获取商城目录，并标记当前用户已安装的条目（按 plugin_name == 目录 id 匹配）
    """
    catalog = load_catalog()
    result = await db.execute(
        select(MCPPlugin.id, MCPPlugin.plugin_name, MCPPlugin.status).where(
            MCPPlugin.user_id == user.user_id,
            MCPPlugin.plugin_name.in_([item.id for item in catalog]),
        )
    )
    installed = {plugin_name: (plugin_id, status) for plugin_id, plugin_name, status in result.all()}

    items = []
    for item in catalog:
        plugin_id, status = installed.get(item.id, (None, None))
        items.append(MCPMarketplaceItemResponse(
            **item.model_dump(exclude={"server"}),
            server_url=str(item.server["url"]),
            installed_plugin_id=plugin_id,
            installed_status=status,
        ))
    return MCPMarketplaceListResponse(categories=CATEGORIES, items=items)


@router.post("/{item_id}/install", response_model=MCPPluginResponse)
async def install_marketplace_item(
    item_id: str,
    data: MCPMarketplaceInstallRequest,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """
    一键安装：用用户填写的 inputs 渲染目录模板 → 创建（或更新已存在的同名）插件并加载
    """
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"商城中不存在该条目: {item_id}")

    try:
        server_config = render_server_config(item, data.inputs)
    except MarketplaceInputError as e:
        raise HTTPException(status_code=400, detail=str(e))

    plugin_data = parse_server_config(item.id, server_config)
    plugin = await upsert_plugin(
        db, user.user_id, plugin_data,
        category=item.category, enabled=data.enabled,
        display_name=item.name, description=item.description,
    )
    logger.info(f"用户 {user.user_id} 从商城安装插件: {item.id} (status={plugin.status})")
    return plugin
