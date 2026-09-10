"""公告弹窗（登录用户侧）：拉取生效视图、取管理员上传的图片。管理端读写在 admin.py。"""
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.deps import require_login
from app.services import announcement_service
from app.services.announcement_service import announcement_store

router = APIRouter(prefix="/announcement", tags=["公告弹窗"])

_IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$")


@router.get("", summary="获取当前生效的公告弹窗")
async def get_announcement(request: Request):
    """不生效（关闭 / 未到开始 / 已过期）时只返回 {active: false}，不泄露未发布内容。"""
    require_login(request)
    settings = await announcement_store.get()
    return settings.to_public_view(datetime.now(timezone.utc))


@router.get("/image/{name}", summary="公告图片（管理员上传）")
async def get_announcement_image(name: str, request: Request):
    require_login(request)
    if not _IMAGE_NAME.match(name):
        raise HTTPException(status_code=400, detail="非法的图片名")
    path = os.path.join(announcement_service.IMAGE_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)
