"""
用户密码管理模块 - 使用数据库存储
"""
import asyncio
import hashlib
from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings


class UserPasswordManager:
    """用户密码管理器 - 使用数据库存储（PostgreSQL共享库）"""
    
    def __init__(self):
        """初始化密码管理器"""
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
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    async def set_password(self, user_id: str, username: str, password: Optional[str] = None) -> str:
        """
        设置用户密码
        
        Args:
            user_id: 用户ID
            username: 用户名
            password: 密码，如果为None则使用默认密码（username+@666）
            
        Returns:
            实际使用的密码（明文，仅用于首次设置时返回给用户）
        """
        from app.models.user import UserPassword as UserPasswordModel
        
        # 如果没有提供密码，使用默认密码
        actual_password = password if password else f"{username}@666"
        
        async with await self._get_session() as session:
            # 查询密码记录是否存在
            result = await session.execute(
                select(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            pwd_record = result.scalar_one_or_none()
            
            if pwd_record:
                # 更新现有密码
                pwd_record.username = username
                pwd_record.password_hash = self._hash_password(actual_password)
                pwd_record.has_custom_password = password is not None
                pwd_record.updated_at = datetime.now()
            else:
                # 创建新密码记录
                pwd_record = UserPasswordModel(
                    user_id=user_id,
                    username=username,
                    password_hash=self._hash_password(actual_password),
                    has_custom_password=password is not None,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(pwd_record)
            
            await session.commit()
            
            return actual_password
    
    async def verify_password(self, user_id: str, password: str) -> bool:
        """
        验证用户密码
        
        Args:
            user_id: 用户ID
            password: 待验证的密码
            
        Returns:
            是否验证通过
        """
        from app.models.user import UserPassword as UserPasswordModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            pwd_record = result.scalar_one_or_none()
            
            if not pwd_record:
                return False
            
            password_hash = self._hash_password(password)
            return pwd_record.password_hash == password_hash
    
    async def has_password(self, user_id: str) -> bool:
        """
        检查用户是否已设置密码
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否已设置密码
        """
        from app.models.user import UserPassword as UserPasswordModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            pwd_record = result.scalar_one_or_none()
            
            return pwd_record is not None
    
    async def has_custom_password(self, user_id: str) -> bool:
        """
        检查用户是否设置了自定义密码（非默认密码）
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否使用自定义密码
        """
        from app.models.user import UserPassword as UserPasswordModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            pwd_record = result.scalar_one_or_none()
            
            if not pwd_record:
                return False
            
            return pwd_record.has_custom_password
    
    async def get_username(self, user_id: str) -> Optional[str]:
        """
        获取用户名
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户名，如果不存在返回None
        """
        from app.models.user import UserPassword as UserPasswordModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            pwd_record = result.scalar_one_or_none()
            
            if not pwd_record:
                return None
            
            return pwd_record.username


# 全局密码管理器实例
password_manager = UserPasswordManager()