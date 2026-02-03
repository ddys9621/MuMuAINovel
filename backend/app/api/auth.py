"""
认证 API - LinuxDO OAuth2 登录 + 本地账户登录
"""
from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, Dict
import hashlib
import time
from datetime import datetime, timedelta, timezone
from app.services.oauth_service import LinuxDOOAuthService
from app.user_manager import user_manager
from app.user_password import password_manager
from app.database import init_db
from app.logger import get_logger
from app.config import settings

# 中国时区 UTC+8
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_now():
    """获取中国当前时间"""
    return datetime.now(CHINA_TZ)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

# OAuth2 服务实例
oauth_service = LinuxDOOAuthService()

# State 临时存储，带过期时间（5分钟）
# 格式: {state: expire_timestamp}
_state_storage: Dict[str, float] = {}
_STATE_EXPIRE_SECONDS = 300  # 5分钟


def _cleanup_expired_states():
    """清理过期的OAuth state，防止内存���漏"""
    current_time = time.time()
    expired_states = [
        state for state, expire_time in _state_storage.items()
        if current_time > expire_time
    ]
    for state in expired_states:
        del _state_storage[state]
    if expired_states:
        logger.debug(f"清理了 {len(expired_states)} 个过期的OAuth state")


class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str


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
        "linuxdo_enabled": bool(settings.LINUXDO_CLIENT_ID and settings.LINUXDO_CLIENT_SECRET)
    }


@router.post("/local/login", response_model=LocalLoginResponse)
async def local_login(request: LocalLoginRequest, response: Response):
    """本地账户登录（支持.env配置的管理员账号和Linux DO授权后绑定的账号）"""
    # 检查是否启用本地登录
    if not settings.LOCAL_AUTH_ENABLED:
        raise HTTPException(status_code=403, detail="本地账户登录未启用")
    
    logger.info(f"[本地登录] 尝试登录用户名: {request.username}")
    
    # 首先尝试查找 Linux DO 授权后绑定的账号
    all_users = await user_manager.get_all_users()
    target_user = None
    
    for user in all_users:
        # 同时检查 users 表的 username 和 user_passwords 表的 username
        password_username = await password_manager.get_username(user.user_id)
        if user.username == request.username or password_username == request.username:
            target_user = user
            logger.info(f"[本地登录] 找到 Linux DO 授权用户: {user.user_id}")
            break
    
    # 如果找到了 Linux DO 授权的用户
    if target_user:
        # 检查是否有密码
        if not await password_manager.has_password(target_user.user_id):
            logger.warning(f"[本地登录] 用户 {target_user.user_id} 没有设置密码")
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 验证密码
        if not await password_manager.verify_password(target_user.user_id, request.password):
            logger.warning(f"[本地登录] 用户 {target_user.user_id} 密码验证失败")
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        logger.info(f"[本地登录] Linux DO 授权用户 {target_user.user_id} 登录成功")
        user = target_user
    else:
        # 没有找到 Linux DO 用户，尝试 .env 配置的管理员账号
        logger.info(f"[本地登录] 未找到 Linux DO 用户，检查 .env 管理员账号")
        
        # 检查是否配置了本地账户
        if not settings.LOCAL_AUTH_USERNAME or not settings.LOCAL_AUTH_PASSWORD:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 生成本地用户ID（使用用户名的hash）
        user_id = f"local_{hashlib.md5(request.username.encode()).hexdigest()[:16]}"
        
        # 检查用户是否存在
        user = await user_manager.get_user(user_id)
        
        # 如果用户不存在，使用.env中的默认密码验证
        if not user:
            # 验证用户名和密码（使用.env配置）
            if request.username != settings.LOCAL_AUTH_USERNAME or request.password != settings.LOCAL_AUTH_PASSWORD:
                raise HTTPException(status_code=401, detail="用户名或密码错误")
            
            # 创建本地用户
            user = await user_manager.create_or_update_from_linuxdo(
                linuxdo_id=user_id,
                username=request.username,
                display_name=settings.LOCAL_AUTH_DISPLAY_NAME,
                avatar_url=None,
                trust_level=9  # 本地用户给予高信任级别
            )
            
            # 为新用户设置默认密码到数据库
            await password_manager.set_password(user.user_id, request.username, request.password)
            logger.info(f"[本地登录] 管理员用户 {user.user_id} 初始密码已设置到数据库")
        else:
            # 用户已存在，使用数据库中的密码验证
            if not await password_manager.verify_password(user.user_id, request.password):
                raise HTTPException(status_code=401, detail="用户名或密码错误")
            
            logger.info(f"[本地登录] 管理员用户 {user.user_id} 登录成功")
    
    # 初始化用户数据库
    try:
        await init_db(user.user_id)
        logger.info(f"本地用户 {user.user_id} 数据库初始化成功")
    except Exception as e:
        logger.error(f"本地用户 {user.user_id} 数据库初始化失败: {e}")
    
    # 设置 Cookie（2小时有效）
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="user_id",
        value=user.user_id,
        max_age=max_age,
        httponly=True,
        samesite="lax"
    )
    
    # 设置过期时间戳 Cookie（用于前端判断）
    china_now = get_china_now()
    expire_time = china_now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())
    
    logger.info(f"✅ [登录] 用户 {user.user_id} 登录成功，会话有效期 {settings.SESSION_EXPIRE_MINUTES} 分钟")
    
    response.set_cookie(
        key="session_expire_at",
        value=str(expire_at),
        max_age=max_age,
        httponly=False,  # 前端需要读取
        samesite="lax"
    )
    
    return LocalLoginResponse(
        success=True,
        message="登录成功",
        user=user.dict()
    )


@router.get("/linuxdo/url", response_model=AuthUrlResponse)
async def get_linuxdo_auth_url():
    """获取 LinuxDO 授权 URL"""
    # 清理过期的state，防止内存泄漏
    _cleanup_expired_states()

    state = oauth_service.generate_state()
    auth_url = oauth_service.get_authorization_url(state)

    # 存储 state 和过期时间
    _state_storage[state] = time.time() + _STATE_EXPIRE_SECONDS

    return AuthUrlResponse(auth_url=auth_url, state=state)


async def _handle_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    response: Response = None
):
    """
    LinuxDO OAuth2 回调处理
    
    成功后重定向到前端首页，并设置 user_id Cookie
    """
    # 检查是否有错误
    if error:
        raise HTTPException(status_code=400, detail=f"授权失败: {error}")
    
    # 检查必需参数
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state 参数")

    # 验证 state（防止 CSRF）
    if state not in _state_storage:
        raise HTTPException(status_code=400, detail="无效的 state 参数")

    # 检查 state 是否过期
    if time.time() > _state_storage[state]:
        del _state_storage[state]
        raise HTTPException(status_code=400, detail="授权已过期，请重新登录")

    # 删除已使用的 state
    del _state_storage[state]

    # 1. 使用 code 获取 access_token
    token_data = await oauth_service.get_access_token(code)
    if not token_data or "access_token" not in token_data:
        raise HTTPException(status_code=400, detail="获取访问令牌失败")
    
    access_token = token_data["access_token"]
    
    # 2. 使用 access_token 获取用户信息
    user_info = await oauth_service.get_user_info(access_token)
    if not user_info:
        raise HTTPException(status_code=400, detail="获取用户信息失败")
    
    # 3. 创建或更新用户
    linuxdo_id = str(user_info.get("id"))
    username = user_info.get("username", "")
    display_name = user_info.get("name", username)
    avatar_url = user_info.get("avatar_url")
    trust_level = user_info.get("trust_level", 0)
    
    user = await user_manager.create_or_update_from_linuxdo(
        linuxdo_id=linuxdo_id,
        username=username,
        display_name=display_name,
        avatar_url=avatar_url,
        trust_level=trust_level
    )
    
    # 3.1. 自动绑定密码（如果还没有设置）
    if not await password_manager.has_password(user.user_id):
        default_password = await password_manager.set_password(user.user_id, username)
        logger.info(f"用户 {user.user_id} ({username}) 自动绑定默认密码: {default_password}")
    
    # 3.5. 初始化用户数据库（如果是新用户）
    try:
        await init_db(user.user_id)
        logger.info(f"用户 {user.user_id} 数据库初始化成功")
    except Exception as e:
        logger.error(f"用户 {user.user_id} 数据库初始化失败: {e}")
        # 继续执行，不影响登录流程（可能是已存在的用户）
    
    # 4. 设置 Cookie 并重定向到前端回调页面
    # 使用配置的前端URL，支持不同的部署环境
    frontend_url = settings.FRONTEND_URL.rstrip('/')
    redirect_url = f"{frontend_url}/auth/callback"
    logger.info(f"OAuth回调成功，重定向到前端: {redirect_url}")
    redirect_response = RedirectResponse(url=redirect_url)
    
    # 设置 httponly Cookie（2小时有效）
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    redirect_response.set_cookie(
        key="user_id",
        value=user.user_id,
        max_age=max_age,
        httponly=True,
        samesite="lax"
    )
    
    # 设置过期时间戳 Cookie（用于前端判断）
    china_now = get_china_now()
    expire_time = china_now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())
    
    logger.info(f"✅ [OAuth登录] 用户 {user.user_id} 登录成功，会话有效期 {settings.SESSION_EXPIRE_MINUTES} 分钟")
    
    redirect_response.set_cookie(
        key="session_expire_at",
        value=str(expire_at),
        max_age=max_age,
        httponly=False,  # 前端需要读取
        samesite="lax"
    )
    
    return redirect_response


@router.get("/linuxdo/callback")
async def linuxdo_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    response: Response = None
):
    """LinuxDO OAuth2 回调处理（标准路径）"""
    return await _handle_callback(code, state, error, response)


@router.get("/callback")
async def callback_alias(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    response: Response = None
):
    """LinuxDO OAuth2 回调处理（兼容路径）"""
    return await _handle_callback(code, state, error, response)


@router.post("/refresh")
async def refresh_session(request: Request, response: Response):
    """刷新会话 - 延长登录状态"""
    # 检查是否已登录
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="未登录，无法刷新会话")
    
    user = request.state.user
    
    # 检查当前会话是否即将过期（剩余时间少于阈值）
    session_expire_at = request.cookies.get("session_expire_at")
    if session_expire_at:
        try:
            expire_timestamp = int(session_expire_at)
            current_timestamp = int(get_china_now().timestamp())
            remaining_minutes = (expire_timestamp - current_timestamp) / 60
            
            # 如果剩余时间大于刷新阈值，不需要刷新
            if remaining_minutes > settings.SESSION_REFRESH_THRESHOLD_MINUTES:
                logger.info(f"⏱️ [刷新会话] 用户 {user.user_id} 会话仍有效，剩余 {int(remaining_minutes)} 分钟")
                return {
                    "message": "会话仍然有效，无需刷新",
                    "remaining_minutes": int(remaining_minutes),
                    "expire_at": expire_timestamp
                }
        except (ValueError, TypeError):
            pass  # Cookie 格式错误，继续刷新
    
    # 刷新 Cookie
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="user_id",
        value=user.user_id,
        max_age=max_age,
        httponly=True,
        samesite="lax"
    )
    
    # 更新过期时间戳
    china_now = get_china_now()
    expire_time = china_now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())
    
    logger.info(f"[刷新会话] 用户: {user.user_id}")
    logger.info(f"[刷新会话] 中国当前时间: {china_now.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    logger.info(f"[刷新会话] 中国过期时间: {expire_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    logger.info(f"[刷新会话] 过期时间戳 (秒): {expire_at}")
    logger.info(f"[刷新会话] Cookie max_age (秒): {max_age}")
    
    response.set_cookie(
        key="session_expire_at",
        value=str(expire_at),
        max_age=max_age,
        httponly=False,
        samesite="lax"
    )
    
    logger.info(f"用户 {user.user_id} 刷新会话成功")
    return {
        "message": "会话刷新成功",
        "expire_at": expire_at,
        "remaining_minutes": settings.SESSION_EXPIRE_MINUTES
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """退出登录"""
    user_id = getattr(request.state, 'user_id', None)
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
    
    # 如果使用默认密码，返回默认密码供用户查看
    default_password = None
    if has_password and not has_custom:
        default_password = f"{user.username}@666"
    
    return PasswordStatusResponse(
        has_password=has_password,
        has_custom_password=has_custom,
        username=username or user.username,
        default_password=default_password
    )


@router.post("/password/set", response_model=SetPasswordResponse)
async def set_user_password(request: Request, password_req: SetPasswordRequest):
    """设置当前用户的密码"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="未登录")
    
    user = request.state.user
    
    # 验证密码强度（至少6个字符）
    if len(password_req.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少为6个字符")
    
    # 设置密码
    await password_manager.set_password(user.user_id, user.username, password_req.password)
    logger.info(f"用户 {user.user_id} ({user.username}) 设置了自定义密码")
    
    return SetPasswordResponse(
        success=True,
        message="密码设置成功"
    )


@router.post("/bind/login", response_model=LocalLoginResponse)
async def bind_account_login(request: LocalLoginRequest, response: Response):
    """使用绑定的账号密码登录（LinuxDO授权后绑定的账号）"""
    # 查找用户
    all_users = await user_manager.get_all_users()
    target_user = None
    
    logger.info(f"[绑定账号登录] 尝试登录用户名: {request.username}")
    logger.info(f"[绑定账号登录] 当前共有 {len(all_users)} 个用户")
    
    for user in all_users:
        # 同时检查 users 表的 username 和 user_passwords 表的 username
        password_username = await password_manager.get_username(user.user_id)
        logger.info(f"[绑定账号登录] 检查用户 {user.user_id}: users.username={user.username}, passwords.username={password_username}")
        
        if user.username == request.username or password_username == request.username:
            target_user = user
            logger.info(f"[绑定账号登录] 找到匹配用户: {user.user_id}")
            break
    
    if not target_user:
        logger.warning(f"[绑定账号登录] 用户名 {request.username} 未找到")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 检查是否有密码记录
    has_pwd = await password_manager.has_password(target_user.user_id)
    if not has_pwd:
        logger.warning(f"[绑定账号登录] 用户 {target_user.user_id} 没有设置密码")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 验证密码
    is_valid = await password_manager.verify_password(target_user.user_id, request.password)
    logger.info(f"[绑定账号登录] 用户 {target_user.user_id} 密码验证结果: {is_valid}")
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 初始化用户数据库
    try:
        await init_db(target_user.user_id)
        logger.info(f"绑定账号用户 {target_user.user_id} 数据库初始化成功")
    except Exception as e:
        logger.error(f"绑定账号用户 {target_user.user_id} 数据库初始化失败: {e}")
    
    # 设置 Cookie（2小时有效）
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="user_id",
        value=target_user.user_id,
        max_age=max_age,
        httponly=True,
        samesite="lax"
    )
    
    # 设置过期时间戳 Cookie（用于前端判断）
    china_now = get_china_now()
    expire_time = china_now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())
    
    logger.info(f"✅ [绑定账号登录] 用户 {target_user.user_id} ({request.username}) 登录成功，会话有效期 {settings.SESSION_EXPIRE_MINUTES} 分钟")
    
    response.set_cookie(
        key="session_expire_at",
        value=str(expire_at),
        max_age=max_age,
        httponly=False,  # 前端需要读取
        samesite="lax"
    )
    
    return LocalLoginResponse(
        success=True,
        message="登录成功",
        user=target_user.dict()
    )