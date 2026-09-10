"""系统更新 API（exe / docker / source 三种运行形态通用）。

- GET  /api/system/update/info          当前版本与运行形态（登录即可，不联网；侧栏常驻显示用；can_manage 告诉前端要不要展示检查/更新入口）
- GET  /api/system/update/check?force=  检查更新（仅管理员；GitHub 不可达时仍 200，error 字段带原因）
- POST /api/system/update/apply         一键更新（仅管理员；exe 下载安装包并启动向导，source 启动独立更新进程）
- GET  /api/system/update/status        更新任务进度（仅管理员）
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import require_admin, require_login
from app.logger import get_logger
from app.services.update_service import UpdateBusy, UpdateNotApplicable, update_service

logger = get_logger(__name__)

router = APIRouter(prefix="/system/update", tags=["系统更新"])


@router.get("/info")
async def update_info_endpoint(request: Request):
    """当前版本与运行形态（不联网；侧栏常驻显示用）。can_manage = 当前用户是否有权检查/应用更新。"""
    user = require_login(request)
    return {
        "current_version": update_service.current_version,
        "run_mode": update_service.run_mode,
        "can_manage": bool(getattr(user, "is_admin", False)),
    }


@router.get("/check")
async def check_update_endpoint(request: Request, force: bool = Query(False, description="忽略缓存强制联网检查")):
    require_admin(request)
    result = await update_service.check(force=force)
    return result.to_dict()


@router.post("/apply")
async def apply_update_endpoint(request: Request):
    user = require_admin(request)
    try:
        status = await update_service.start_apply()
    except UpdateNotApplicable as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpdateBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    logger.info("用户 %s 触发一键更新（%s）", getattr(user, "user_id", "?"), getattr(update_service, "run_mode", "?"))
    return status


@router.get("/status")
async def update_status_endpoint(request: Request):
    require_admin(request)
    return await update_service.status()
