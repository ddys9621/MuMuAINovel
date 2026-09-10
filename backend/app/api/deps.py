"""API 层公共依赖：登录校验与项目归属校验。

此前 8 个 api 模块各有一份逐字相同的 verify_project_access、5 个模块各有一份 require_login；
统一到这里。plot_bridges 的版本对非本人返回 403，语义不同，保留原地。
"""
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import get_logger
from app.models.project import Project
from app.models.user import User

logger = get_logger(__name__)


def require_login(request: Request) -> User:
    """依赖：要求用户已登录"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="需要登录")
    return request.state.user


def require_admin(request: Request) -> User:
    """依赖：要求管理员（未登录 401，非管理员 403）"""
    user = require_login(request)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def verify_project_access(project_id: str, user_id: str, db: AsyncSession) -> Project:
    """
    验证用户是否有权访问指定项目

    Raises:
        HTTPException: 401 未登录，404 项目不存在或无权访问
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"项目访问被拒绝: project_id={project_id}, user_id={user_id}")
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    return project
