"""
用户管理模块 - 使用数据库存储
"""
import asyncio
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pydantic import BaseModel
from app.config import settings


class User(BaseModel):
    """用户数据传输对象"""
    user_id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    trust_level: int = 0
    is_admin: bool = False
    linuxdo_id: str
    created_at: str
    last_login: str


class UserManager:
    """用户管理器 - 使用数据库存储（PostgreSQL共享库）"""
    
    def __init__(self):
        """初始化用户管理器"""
        pass
    
    async def _get_session(self) -> AsyncSession:
        """获取数据库会话 - 使用共享的PostgreSQL引擎"""
        from app.database import get_engine
        
        # 使用共享的PostgreSQL引擎（user_id使用特殊标识）
        engine = await get_engine("_global_users_")
        
        session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        return session_maker()
    
    async def create_or_update_from_linuxdo(
        self,
        linuxdo_id: str,
        username: str,
        display_name: str,
        avatar_url: Optional[str],
        trust_level: int
    ) -> User:
        """
        从 LinuxDO 用户信息创建或更新用户
        
        Args:
            linuxdo_id: LinuxDO 用户 ID（本地用户时为 local_xxx 格式）
            username: 用户名
            display_name: 显示名称
            avatar_url: 头像 URL
            trust_level: 信任等级
            
        Returns:
            用户对象
        """
        from app.models.user import User as UserModel
        
        # 生成 user_id
        if linuxdo_id.startswith("local_"):
            user_id = linuxdo_id
        else:
            user_id = f"linuxdo_{linuxdo_id}"
        
        async with await self._get_session() as session:
            # 查询用户是否存在
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            # 检查是否为初始管理员或本地用户
            initial_admin_id = settings.INITIAL_ADMIN_LINUXDO_ID
            is_initial_admin = (initial_admin_id and linuxdo_id == initial_admin_id)
            is_local_user = user_id.startswith("local_")
            is_admin = is_initial_admin or is_local_user
            
            if user:
                # 更新现有用户
                user.username = username
                user.display_name = display_name
                user.avatar_url = avatar_url
                user.trust_level = trust_level
                user.last_login = datetime.now()
                
                # 更新管理员状态
                if is_admin and not user.is_admin:
                    user.is_admin = True
            else:
                # 创建新用户
                user = UserModel(
                    user_id=user_id,
                    username=username,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    trust_level=trust_level,
                    is_admin=is_admin,
                    linuxdo_id=linuxdo_id,
                    created_at=datetime.now(),
                    last_login=datetime.now()
                )
                session.add(user)
            
            await session.commit()
            await session.refresh(user)
            
            return User(**user.to_dict())
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                return User(**user.to_dict())
            return None
    
    async def get_all_users(self) -> List[User]:
        """获取所有用户"""
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(select(UserModel))
            users = result.scalars().all()
            
            return [User(**user.to_dict()) for user in users]
    
    async def set_admin(self, user_id: str, is_admin: bool) -> bool:
        """
        设置用户的管理员权限
        
        Args:
            user_id: 用户 ID
            is_admin: 是否为管理员
            
        Returns:
            是否成功
        """
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            if not is_admin:
                # 撤销管理员权限时，确保至少保留一个管理员
                admin_result = await session.execute(
                    select(UserModel).where(UserModel.is_admin == True)
                )
                admin_count = len(admin_result.scalars().all())
                
                if admin_count <= 1:
                    return False
            
            user.is_admin = is_admin
            await session.commit()
            
            return True
    
    async def delete_user(self, user_id: str) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            是否成功
        """
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            # 不能删除管理员
            if user.is_admin:
                return False
            
            await session.delete(user)
            await session.commit()
            
            return True
    
    async def is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            return user.is_admin if user else False


# 全局用户管理器实例
user_manager = UserManager()