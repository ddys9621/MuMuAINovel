"""system_settings 表的通用读写：一个 key 对应一个 pydantic 模型序列化后的 JSON。

登录方式配置（key="auth"）与公告弹窗配置（key="announcement"）共用这一套；
解析失败时回退模型默认值并记日志，不让一条坏数据拖死启动。
"""
from __future__ import annotations

import json
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class JsonSettingsStore(Generic[T]):
    """按 key 存取一段 JSON 配置（与 user_manager 共用全局引擎）"""

    def __init__(self, key: str, model: type[T], label: str = ""):
        self.key = key
        self.model = model
        self.label = label or key

    async def _get_session(self) -> AsyncSession:
        from app.database import get_engine

        engine = await get_engine("_global_users_")
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()

    async def get(self) -> T:
        from app.models.system_setting import SystemSetting

        async with await self._get_session() as session:
            row = await session.get(SystemSetting, self.key)

        if not row or not row.value:
            return self.model()
        try:
            return self.model.model_validate(json.loads(row.value))
        except (ValueError, ValidationError) as e:
            logger.error(f"{self.label}配置解析失败，回退默认值: {e}")
            return self.model()

    async def save(self, settings: T) -> T:
        from app.models.system_setting import SystemSetting

        payload = settings.model_dump_json()
        async with await self._get_session() as session:
            row = await session.get(SystemSetting, self.key)
            if row:
                row.value = payload
            else:
                session.add(SystemSetting(key=self.key, value=payload))
            await session.commit()
        return settings

    async def apply_update(self, update: BaseModel) -> T:
        """部分更新：update 里为 None 的字段保持不变。"""
        current = await self.get()
        changes = update.model_dump(exclude_none=True)
        merged = self.model.model_validate({**current.model_dump(), **changes})
        return await self.save(merged)
