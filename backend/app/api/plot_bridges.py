"""V4.1 K2 桥段 API（Phase 2 P2-4）。

端点：
- POST   /api/projects/{project_id}/bridges/plan          规划 N 个桥段
- GET    /api/projects/{project_id}/bridges               列表
- GET    /api/bridges/{bridge_id}                         详情
- PATCH  /api/bridges/{bridge_id}                         更新（修改 4 章卡片内容）
- DELETE /api/bridges/{bridge_id}                         删除
- POST   /api/bridges/{bridge_id}/expand                  展开为 4 个 ChapterOutline
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.services.ai_service import AIService
from app.services.bridge_planning_service import BridgePlanningService


async def verify_project_access(
    project_id: str, user_id: str | None, db: AsyncSession
) -> Project:
    """统一的项目访问验证（参考其他 api 模块的同名函数）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问此项目")
    return project

logger = logging.getLogger(__name__)

router = APIRouter(tags=["桥段四章 K2"])


# ============================================================
# Schemas
# ============================================================

class PlanBridgesRequest(BaseModel):
    """规划桥段请求。"""
    bridge_count: int = Field(default=25, ge=1, le=300)
    model: Optional[str] = Field(default=None, description="覆盖默认模型")


class ExpandBridgeRequest(BaseModel):
    """展开桥段请求。"""
    start_chapter_number: int = Field(..., ge=1)
    model: Optional[str] = Field(default=None)


class UpdateBridgeRequest(BaseModel):
    title: Optional[str] = None
    goal: Optional[str] = None
    showoff_point: Optional[str] = None
    golden_finger_usage: Optional[str] = None
    c1_intro: Optional[str] = None
    c2_build: Optional[str] = None
    c3_payoff: Optional[str] = None
    c4_aftermath: Optional[str] = None
    next_bridge_hook: Optional[str] = None
    status: Optional[str] = None


class BridgeResponse(BaseModel):
    id: str
    project_id: str
    bridge_number: int
    title: str
    goal: str
    showoff_point: str
    golden_finger_usage: Optional[str]
    c1_intro: Optional[str]
    c2_build: Optional[str]
    c3_payoff: Optional[str]
    c4_aftermath: Optional[str]
    next_bridge_hook: Optional[str]
    status: str
    order_index: Optional[int]

    class Config:
        from_attributes = True


# ============================================================
# 依赖
# ============================================================

def get_bridge_service(request: Request) -> BridgePlanningService:
    """从 request.state 注入 AI service（中间件已注入）。"""
    user_ai = getattr(request.state, "user_ai_service", None)
    if not user_ai:
        # fallback：用默认 AIService（依赖 settings）
        user_ai = AIService()
    return BridgePlanningService(ai_service=user_ai)


# ============================================================
# Routes
# ============================================================

@router.post("/projects/{project_id}/bridges/plan", response_model=list[BridgeResponse])
async def plan_bridges_endpoint(
    project_id: str,
    payload: PlanBridgesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """规划 N 个桥段（自动注入拆书 bridges + synopsis + methodology 维度）。"""
    user_id = getattr(request.state, "user_id", None)
    await verify_project_access(project_id, user_id, db)

    service = get_bridge_service(request)
    model = payload.model or "deepseek-v3"  # 默认模型
    try:
        bridges = await service.plan_bridges(
            db,
            project_id=project_id,
            model_name=model,
            bridge_count=payload.bridge_count,
        )
    except Exception as exc:
        logger.error("[plot_bridges] 规划失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"桥段规划失败: {exc}")

    return [BridgeResponse.model_validate(b) for b in bridges]


@router.get("/projects/{project_id}/bridges", response_model=list[BridgeResponse])
async def list_bridges_endpoint(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """列出项目下所有桥段（按 order_index）。"""
    user_id = getattr(request.state, "user_id", None)
    await verify_project_access(project_id, user_id, db)

    service = get_bridge_service(request)
    bridges = await service.list_bridges(db, project_id)
    return [BridgeResponse.model_validate(b) for b in bridges]


@router.get("/bridges/{bridge_id}", response_model=BridgeResponse)
async def get_bridge_endpoint(
    bridge_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = get_bridge_service(request)
    bridge = await service.get_bridge(db, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="桥段不存在")

    user_id = getattr(request.state, "user_id", None)
    await verify_project_access(bridge.project_id, user_id, db)
    return BridgeResponse.model_validate(bridge)


@router.patch("/bridges/{bridge_id}", response_model=BridgeResponse)
async def update_bridge_endpoint(
    bridge_id: str,
    payload: UpdateBridgeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """用户手工编辑桥段卡片内容。"""
    service = get_bridge_service(request)
    bridge = await service.get_bridge(db, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="桥段不存在")

    user_id = getattr(request.state, "user_id", None)
    await verify_project_access(bridge.project_id, user_id, db)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            setattr(bridge, key, value)
    await db.commit()
    await db.refresh(bridge)
    return BridgeResponse.model_validate(bridge)


@router.delete("/bridges/{bridge_id}")
async def delete_bridge_endpoint(
    bridge_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = get_bridge_service(request)
    bridge = await service.get_bridge(db, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="桥段不存在")

    user_id = getattr(request.state, "user_id", None)
    await verify_project_access(bridge.project_id, user_id, db)

    ok = await service.delete_bridge(db, bridge_id)
    return {"success": ok}


@router.post("/bridges/{bridge_id}/expand")
async def expand_bridge_endpoint(
    bridge_id: str,
    payload: ExpandBridgeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """把单个桥段展开为 4 个 ChapterOutline（自动赋 bridge_id + bridge_position）。"""
    service = get_bridge_service(request)
    bridge = await service.get_bridge(db, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="桥段不存在")

    user_id = getattr(request.state, "user_id", None)
    await verify_project_access(bridge.project_id, user_id, db)

    model = payload.model or "deepseek-v3"
    try:
        chapters = await service.expand_bridge_to_chapters(
            db,
            bridge_id=bridge_id,
            model_name=model,
            start_chapter_number=payload.start_chapter_number,
        )
    except Exception as exc:
        logger.error("[plot_bridges] 展开失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"桥段展开失败: {exc}")

    return {
        "success": True,
        "bridge_id": bridge_id,
        "chapter_count": len(chapters),
        "chapter_ids": [c.id for c in chapters],
    }
