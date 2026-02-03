"""
用户管理 API
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.user_manager import user_manager, User
from app.user_password import password_manager

router = APIRouter(prefix="/users", tags=["用户管理"])


def require_login(request: Request):
    """依赖：要求用户已登录"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="需要登录")
    return request.state.user


def require_admin(request: Request):
    """依赖：要求用户为管理员"""
    user = require_login(request)
    if not request.state.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


class SetAdminRequest(BaseModel):
    user_id: str
    is_admin: bool


class ResetPasswordRequest(BaseModel):
    user_id: str
    new_password: Optional[str] = None  # 如果为空则使用默认密码


@router.get("/current")
async def get_current_user(user: User = Depends(require_login)):
    """获取当前登录用户信息"""
    return user.dict()


@router.get("", response_model=List[dict])
async def list_users(admin_user: User = Depends(require_admin)):
    """
    获取所有用户列表（仅管理员）
    """
    users = await user_manager.get_all_users()
    return [user.dict() for user in users]


@router.post("/set-admin")
async def set_admin(
    data: SetAdminRequest,
    request: Request,
    admin_user: User = Depends(require_admin)
):
    """
    设置用户的管理员权限（仅管理员）
    
    限制：
    - 不能撤销自己的管理员权限
    - 至少保留一个管理员
    """
    # 检查是否尝试撤销自己的权限
    if data.user_id == admin_user.user_id and not data.is_admin:
        raise HTTPException(
            status_code=400,
            detail="不能撤销自己的管理员权限"
        )
    
    # 尝试设置管理员权限
    success = await user_manager.set_admin(data.user_id, data.is_admin)
    
    if not success:
        if not data.is_admin:
            raise HTTPException(
                status_code=400,
                detail="无法撤销管理员权限，至少需要保留一个管理员"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="用户不存在"
            )
    
    return {
        "message": f"已{'授予' if data.is_admin else '撤销'}管理员权限",
        "user_id": data.user_id,
        "is_admin": data.is_admin
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    admin_user: User = Depends(require_admin)
):
    """
    删除用户（仅管理员）
    
    限制：
    - 不能删除管理员用户
    """
    success = await user_manager.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="无法删除该用户（用户不存在或为管理员）"
        )
    
    return {
        "message": "用户已删除",
        "user_id": user_id
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    admin_user: User = Depends(require_admin)
):
    """获取指定用户信息（仅管理员）"""
    user = await user_manager.get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user.dict()


@router.post("/reset-password")
async def reset_user_password(
    data: ResetPasswordRequest,
    admin_user: User = Depends(require_admin)
):
    """
    重置用户密码（仅管理员）
    
    如果提供了 new_password，则设置为指定密码
    如果未提供 new_password，则重置为默认密码（username@666）
    
    限制：
    - 不能重置自己的密码（应该使用修改密码功能）
    """
    # 检查是否尝试重置自己的密码
    if data.user_id == admin_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="不能重置自己的密码，请使用修改密码功能"
        )
    
    # 检查目标用户是否存在
    target_user = await user_manager.get_user(data.user_id)
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="目标用户不存在"
        )
    
    # 重置密码
    try:
        actual_password = await password_manager.set_password(
            target_user.user_id,
            target_user.username,
            data.new_password
        )
        
        # 如果使用了默认密码，返回密码供管理员告知用户
        message = "密码重置成功"
        response_data = {
            "message": message,
            "user_id": data.user_id,
            "username": target_user.username
        }
        
        if not data.new_password:
            response_data["default_password"] = actual_password
            response_data["message"] = f"密码已重置为默认密码: {actual_password}"
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"重置密码失败: {str(e)}"
        )