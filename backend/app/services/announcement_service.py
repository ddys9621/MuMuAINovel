"""公告弹窗配置：system_settings 表 key="announcement" 的一段 JSON。

管理员可改标题 / 正文 / 图片 / 按钮 / 链接 / 显示频率 / 起止时间；登录用户拉取「生效视图」：
是否在时间窗内由服务器时间判定，revision 是展示字段的哈希——内容一改就换，前端据此决定
「只弹一次」的用户要不要再弹；开关、时间、频率只是调度，不改变 revision。
时间一律按 UTC 存（naive 视为 UTC），前端用 datetime-local 输入后转 ISO 提交。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.logger import get_logger
from app.services.system_settings_store import JsonSettingsStore
from app.utils.runtime_paths import runtime_base_dir

logger = get_logger(__name__)

ANNOUNCEMENT_KEY = "announcement"
Frequency = Literal["once", "daily", "always"]

# 展示字段：决定 revision 的那部分
DISPLAY_FIELDS = ("badge", "title", "content", "image_url", "button_text", "link_text", "link_url")

# 上传图片存放处与对外 URL 前缀（与 data/mumuai.db 同级，exe 升级不会被清）
IMAGE_DIR = os.path.join(runtime_base_dir(), "data", "announcement")
IMAGE_URL_PREFIX = "/api/announcement/image/"
MAX_IMAGE_BYTES = 2 * 1024 * 1024
_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def sniff_image_ext(data: bytes) -> Optional[str]:
    """按文件头识别 jpg/png/gif/webp，不信任 Content-Type；识别不了返回 None。"""
    for magic, ext in _IMAGE_MAGIC:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AnnouncementSettings(BaseModel):
    """管理员可配置的公告弹窗全集（默认值 = 升级前写死的交流群弹窗，行为不变）"""
    enabled: bool = True
    badge: str = Field("官方交流群", max_length=30)
    title: str = Field("加入交流群", max_length=60)
    content: str = Field("扫码加入开发交流群，获取更新通知、使用答疑和创作交流。", max_length=2000)
    image_url: str = Field("/dev-group-qr.jpg", max_length=500)
    button_text: str = Field("我知道了", max_length=20)
    link_text: str = Field("", max_length=40)
    link_url: str = Field("", max_length=500)
    frequency: Frequency = "once"
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    @field_validator("badge", "title", "content", "image_url", "button_text", "link_text", "link_url", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("start_at", "end_at", mode="after")
    @classmethod
    def _utc(cls, value):
        return _ensure_utc(value)

    @model_validator(mode="after")
    def _window_order(self):
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("开始时间不能晚于结束时间")
        return self

    def is_active(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if self.start_at and now < self.start_at:
            return False
        if self.end_at and now > self.end_at:
            return False
        return True

    def revision(self) -> str:
        payload = json.dumps({f: getattr(self, f) for f in DISPLAY_FIELDS}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    def to_public_view(self, now: datetime) -> dict:
        """登录用户看到的：不生效时只给 active=False，不泄露未发布的内容。"""
        if not self.is_active(now):
            return {"active": False}
        view = {f: getattr(self, f) for f in DISPLAY_FIELDS}
        view.update(active=True, revision=self.revision(), frequency=self.frequency)
        return view

    def to_admin_view(self, now: datetime) -> dict:
        view = self.model_dump(mode="json")
        view.update(active=self.is_active(now), revision=self.revision())
        return view


class AnnouncementUpdate(BaseModel):
    """PUT 请求体：全部可选，None = 不修改；start_at / end_at 传空串 = 清空。"""
    enabled: Optional[bool] = None
    badge: Optional[str] = Field(None, max_length=30)
    title: Optional[str] = Field(None, max_length=60)
    content: Optional[str] = Field(None, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=500)
    button_text: Optional[str] = Field(None, max_length=20)
    link_text: Optional[str] = Field(None, max_length=40)
    link_url: Optional[str] = Field(None, max_length=500)
    frequency: Optional[Frequency] = None
    start_at: Optional[datetime | Literal[""]] = None
    end_at: Optional[datetime | Literal[""]] = None


def is_uploaded_image(url: str) -> bool:
    return url.startswith(IMAGE_URL_PREFIX)


def uploaded_image_path(url: str) -> Optional[str]:
    """把 /api/announcement/image/<name> 映射回磁盘路径；名字只允许 uuid.ext，防目录穿越。"""
    if not is_uploaded_image(url):
        return None
    name = url[len(IMAGE_URL_PREFIX):]
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    return os.path.join(IMAGE_DIR, name)


def remove_uploaded_image(url: str) -> None:
    path = uploaded_image_path(url)
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError as e:
            logger.warning(f"删除旧公告图片失败 {path}: {e}")


class AnnouncementStore(JsonSettingsStore[AnnouncementSettings]):
    """system_settings key="announcement"；换图时顺手删掉被替换的上传文件。"""

    def __init__(self):
        super().__init__(ANNOUNCEMENT_KEY, AnnouncementSettings, "公告弹窗")

    async def apply_update(self, update: AnnouncementUpdate) -> AnnouncementSettings:
        current = await self.get()
        changes = update.model_dump(exclude_none=True)
        for field in ("start_at", "end_at"):
            if changes.get(field) == "":
                changes[field] = None
        merged = AnnouncementSettings.model_validate({**current.model_dump(), **changes})
        saved = await self.save(merged)
        if current.image_url != saved.image_url:
            remove_uploaded_image(current.image_url)
        return saved


# 全局实例
announcement_store = AnnouncementStore()
