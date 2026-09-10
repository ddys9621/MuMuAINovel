"""系统级设置数据模型 - 全局 key/value（与 users 表同库，不按用户隔离）"""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.db_base import Base


class SystemSetting(Base):
    """系统设置表：一个 key 对应一段 JSON 文本（如 key="auth" 存登录方式配置）"""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, comment="设置键")
    value = Column(Text, nullable=False, default="{}", comment="设置值（JSON 文本）")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<SystemSetting(key={self.key})>"
