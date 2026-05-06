"""
Authentication API - local username/password only.
"""
from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
from typing import Optional
import hashlib
from datetime import datetime, timedelta, timezone

from app.user_manager import user_manager
from app.user_password import password_manager
from app.database import init_db
from app.logger import get_logger
from app.config import settings


CHINA_TZ = timezone(timedelta(hours=8))


def get_china_now():
    """获取中国当前时间"""
    return datetime.now(CHINA_TZ)


logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])


class LocalLoginRequest(BaseModel):
    """本地登录请求"""
    username: str
    password: str


class LocalLoginResponse(BaseModel):
    """本地登录响应"""
    success: bool
    message: str
    user: Optional[dict] = None


class SetPasswordRequest(BaseModel):
    """设置密码请求"""
    password: str


class SetPasswordResponse(BaseModel):
    """设置密码响应"""
    success: bool
    message: str


class PasswordStatusResponse(BaseModel):
    """密码状态响应"""
    has_password: bool
    has_custom_password: bool
    username: Optional[str] = None
    default_password: Optional[str] = None


@router.get("/config")
async def get_auth_config():
    """获取认证配置信息"""
    return {
        "local_auth_enabled": settings.LOCAL_AUTH_ENABLED,
        "linuxdo_enabled": False,
    }


def _local_user_id(username: str) -> str:
    return f"local_{hashlib.md5(username.encode()).hexdigest()[:16]}"


async def _create_or_update_local_user(username: str):
    return await user_manager.create_or_update_local_user(
        user_id=_local_user_id(username),
        username=username,
        display_name=settings.LOCAL_AUTH_DISPLAY_NAME,
        avatar_url=None,
        trust_level=9,
        is_admin=True,
    )


async def _authenticate_config_local_account(username: str, password: str):
    """Authenticate the configured local admin account."""
    if not settings.LOCAL_AUTH_USERNAME or not settings.LOCAL_AUTH_PASSWORD:
        return None
    if username != settings.LOCAL_AUTH_USERNAME:
        return None

    user_id = _local_user_id(username)
    user = await user_manager.get_user(user_id)

    if not user:
        if password != settings.LOCAL_AUTH_PASSWORD:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        user = await _create_or_update_local_user(username)
        await password_manager.set_password(user.user_id, username, settings.LOCAL_AUTH_PASSWORD)
        logger.info(f"[本地登录] 配置账号 {user.user_id} 首次登录，已创建本地用户")
        return user

    db_valid = False
    if await password_manager.has_password(user.user_id):
        db_valid = await password_manager.verify_password(user.user_id, password)

    config_valid = password == settings.LOCAL_AUTH_PASSWORD
    if not db_valid and not config_valid:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if config_valid and not db_valid:
        await password_manager.set_password(user.user_id, username, settings.LOCAL_AUTH_PASSWORD)
        logger.info(f"[本地登录] 配置账号 {user.user_id} 密码已同步到数据库")

    logger.info(f"[本地登录] 配置账号 {user.user_id} 登录成功")
    return user


async def _authenticate_database_local_account(username: str, password: str):
    """Authenticate local database accounts by stored username/password."""
    all_users = await user_manager.get_all_users()

    for user in all_users:
        password_username = await password_manager.get_username(user.user_id)
        if user.username != username and password_username != username:
            continue

        if not await password_manager.has_password(user.user_id):
            logger.warning(f"[本地登录] 用户 {user.user_id} 没有设置密码")
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not await password_manager.verify_password(user.user_id, password):
            logger.warning(f"[本地登录] 用户 {user.user_id} 密码验证失败")
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        logger.info(f"[本地登录] 本地账号 {user.user_id} 登录成功")
        return user

    logger.info(f"[本地登录] 未找到匹配的本地账号: {username}")
    return None


async def _set_session_cookies(response: Response, user_id: str):
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="user_id",
        value=user_id,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )

    expire_time = get_china_now() + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())
    response.set_cookie(
        key="session_expire_at",
        value=str(expire_at),
        max_age=max_age,
        httponly=False,
        samesite="lax",
    )


@router.post("/local/login", response_model=LocalLoginResponse)
async def local_login(request: LocalLoginRequest, response: Response):
    """本地账户登录"""
    if not settings.LOCAL_AUTH_ENABLED:
        raise HTTPException(status_code=403, detail="本地账户登录未启用")

    logger.info(f"[本地登录] 尝试登录用户名: {request.username}")

    user = await _authenticate_config_local_account(request.username, request.password)
    if not user:
        user = await _authenticate_database_local_account(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    try:
        await init_db(user.user_id)
        logger.info(f"本地用户 {user.user_id} 数据库初始化成功")
    except Exception as e:
        logger.error(f"本地用户 {user.user_id} 数据库初始化失败: {e}")

    await _set_session_cookies(response, user.user_id)
    logger.info(f"✅ [登录] 用户 {user.user_id} 登录成功，会话有效期 {settings.SESSION_EXPIRE_MINUTES} 分钟")

    return LocalLoginResponse(
        success=True,
        message="登录成功",
        user=user.dict(),
    )


@router.post("/refresh")
async def refresh_session(request: Request, response: Response):
    """刷新会话 - 延长登录状态"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="未登录，无法刷新会话")

    user = request.state.user

    session_expire_at = request.cookies.get("session_expire_at")
    if session_expire_at:
        try:
            expire_timestamp = int(session_expire_at)
            current_timestamp = int(get_china_now().timestamp())
            remaining_minutes = (expire_timestamp - current_timestamp) / 60

            if remaining_minutes > settings.SESSION_REFRESH_THRESHOLD_MINUTES:
                logger.info(f"⏱️ [刷新会话] 用户 {user.user_id} 会话仍有效，剩余 {int(remaining_minutes)} 分钟")
                return {
                    "message": "会话仍然有效，无需刷新",
                    "remaining_minutes": int(remaining_minutes),
                    "expire_at": expire_timestamp,
                }
        except (ValueError, TypeError):
            pass

    await _set_session_cookies(response, user.user_id)
    expire_at = int((get_china_now() + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)).timestamp())

    logger.info(f"用户 {user.user_id} 刷新会话成功")
    return {
        "message": "会话刷新成功",
        "expire_at": expire_at,
        "remaining_minutes": settings.SESSION_EXPIRE_MINUTES,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """退出登录"""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        logger.info(f"🚪 [退出] 用户 {user_id} 退出登录")

    response.delete_cookie("user_id")
    response.delete_cookie("session_expire_at")
    return {"message": "退出登录成功"}


@router.get("/user")
async def get_current_user(request: Request):
    """获取当前登录用户信息"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="未登录")

    return request.state.user.dict()


@router.get("/password/status", response_model=PasswordStatusResponse)
async def get_password_status(request: Request):
    """获取当前用户的密码状态"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="未登录")

    user = request.state.user
    has_password = await password_manager.has_password(user.user_id)
    has_custom = await password_manager.has_custom_password(user.user_id)
    username = await password_manager.get_username(user.user_id)

    default_password = None
    if has_password and not has_custom:
        default_password = f"{user.username}@666"

    return PasswordStatusResponse(
        has_password=has_password,
        has_custom_password=has_custom,
        username=username or user.username,
        default_password=default_password,
    )


@router.post("/password/set", response_model=SetPasswordResponse)
async def set_user_password(request: Request, password_req: SetPasswordRequest):
    """设置当前用户的密码"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="未登录")

    user = request.state.user

    if len(password_req.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少为6个字符")

    await password_manager.set_password(user.user_id, user.username, password_req.password)
    logger.info(f"用户 {user.user_id} ({user.username}) 设置了自定义密码")

    return SetPasswordResponse(
        success=True,
        message="密码设置成功",
    )
