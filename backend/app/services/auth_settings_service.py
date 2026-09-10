"""登录方式配置：Linux.do OAuth / 邮箱注册登录 / SMTP —— 存 system_settings 表 key="auth" 的一段 JSON。

有效开关（effective_flags）= 管理员开关 && 凭据齐全 && 对应的登录开关开着（注册依赖登录）。
秘密字段（client_secret / smtp_password）不回传前端，管理视图只给 *_set 布尔；
PUT 时秘密字段为 None 表示不改，空串才是清空。
"""
from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.logger import get_logger

logger = get_logger(__name__)

AUTH_SETTINGS_KEY = "auth"
SECRET_FIELDS = ("linuxdo_client_secret", "smtp_password")

SmtpEncryption = Literal["ssl", "starttls", "none"]


class _StripStrings(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class AuthSettings(_StripStrings):
    """管理员可配置的登录方式全集（含秘密字段，仅后端内部使用）"""
    linuxdo_login_enabled: bool = False
    linuxdo_register_enabled: bool = False
    linuxdo_client_id: str = ""
    linuxdo_client_secret: str = ""
    linuxdo_redirect_uri: str = ""

    email_login_enabled: bool = False
    email_register_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(465, ge=1, le=65535)
    smtp_encryption: SmtpEncryption = "ssl"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    def linuxdo_configured(self) -> bool:
        return bool(self.linuxdo_client_id and self.linuxdo_client_secret and self.linuxdo_redirect_uri)

    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    def effective_flags(self) -> dict[str, bool]:
        """对外生效的四个开关：登录要凭据齐全，注册还要对应登录开着；邮箱注册额外要 SMTP。"""
        linuxdo_login = self.linuxdo_login_enabled and self.linuxdo_configured()
        email_login = self.email_login_enabled
        return {
            "linuxdo_login_enabled": linuxdo_login,
            "linuxdo_register_enabled": linuxdo_login and self.linuxdo_register_enabled,
            "email_login_enabled": email_login,
            "email_register_enabled": email_login and self.email_register_enabled and self.smtp_configured(),
        }

    def to_admin_view(self) -> dict:
        """给管理后台的视图：去掉秘密字段，附 <secret>_set 表示是否已设置。"""
        view = self.model_dump(exclude=set(SECRET_FIELDS))
        for field in SECRET_FIELDS:
            view[f"{field}_set"] = bool(getattr(self, field))
        return view


class AuthSettingsUpdate(_StripStrings):
    """PUT 请求体：全部可选，None = 不修改。"""
    linuxdo_login_enabled: Optional[bool] = None
    linuxdo_register_enabled: Optional[bool] = None
    linuxdo_client_id: Optional[str] = None
    linuxdo_client_secret: Optional[str] = None
    linuxdo_redirect_uri: Optional[str] = None

    email_login_enabled: Optional[bool] = None
    email_register_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_encryption: Optional[SmtpEncryption] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None


class AuthSettingsStore:
    """system_settings 表 key="auth" 的读写（与 user_manager 共用全局引擎）"""

    async def _get_session(self) -> AsyncSession:
        from app.database import get_engine

        engine = await get_engine("_global_users_")
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()

    async def get(self) -> AuthSettings:
        from app.models.system_setting import SystemSetting

        async with await self._get_session() as session:
            row = await session.get(SystemSetting, AUTH_SETTINGS_KEY)

        if not row or not row.value:
            return AuthSettings()
        try:
            return AuthSettings.model_validate(json.loads(row.value))
        except (ValueError, ValidationError) as e:
            logger.error(f"登录方式配置解析失败，回退默认值: {e}")
            return AuthSettings()

    async def save(self, settings: AuthSettings) -> AuthSettings:
        from app.models.system_setting import SystemSetting

        payload = settings.model_dump_json()
        async with await self._get_session() as session:
            row = await session.get(SystemSetting, AUTH_SETTINGS_KEY)
            if row:
                row.value = payload
            else:
                session.add(SystemSetting(key=AUTH_SETTINGS_KEY, value=payload))
            await session.commit()
        return settings

    async def apply_update(self, update: AuthSettingsUpdate) -> AuthSettings:
        current = await self.get()
        changes = update.model_dump(exclude_none=True)
        merged = AuthSettings.model_validate({**current.model_dump(), **changes})
        return await self.save(merged)


# 全局实例
auth_settings_store = AuthSettingsStore()
