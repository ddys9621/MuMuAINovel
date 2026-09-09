"""MCP 商城内置目录

目录数据在同目录 marketplace_catalog.json（手工维护，tests/test_mcp_marketplace_catalog.py 做完整性校验）。
每条目录项是一个远程 MCP 服务模板：server 里的 `{{KEY}}` 占位符在安装时用用户填写的 inputs 替换，
再交给 server_config.parse_server_config() 归一化落库。
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.mcp.server_config import TRANSPORT_SSE, TRANSPORT_STREAMABLE_HTTP

_CATALOG_PATH = Path(__file__).with_name("marketplace_catalog.json")
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

# 展示顺序即列表顺序
CATEGORIES: List[Dict[str, str]] = [
    {"id": "search_cn", "label": "国内联网搜索"},
    {"id": "search_global", "label": "国际搜索与网页抓取"},
    {"id": "knowledge", "label": "知识与参考"},
]


class MarketplaceInput(BaseModel):
    """安装时需要用户填写的一项（通常是 API Key）"""
    key: str = Field(..., description="占位符名，如 ZHIPU_API_KEY")
    label: str = Field(..., description="表单标签")
    required: bool = True
    secret: bool = True
    placeholder: Optional[str] = None
    help_url: Optional[str] = Field(None, description="去哪里获取 / 开通")
    help_label: Optional[str] = Field(None, description="链接文案，缺省由前端显示「获取 Key」")
    help_text: Optional[str] = Field(None, description="免费额度 / 注意事项")


class MarketplaceItem(BaseModel):
    """一条可一键安装的远程 MCP 服务"""
    id: str
    name: str
    description: str
    category: str
    tags: List[str] = Field(default_factory=list)
    transport: Literal["streamable_http", "sse"]
    server: Dict[str, Any] = Field(..., description="mcpServers 片段模板：url / headers，可含 {{KEY}} 占位符")
    inputs: List[MarketplaceInput] = Field(default_factory=list)
    homepage: str
    official: bool = False
    region: Literal["cn", "global"]
    pricing: str
    notes: Optional[str] = None
    recommended: bool = False
    verified_at: Optional[str] = Field(None, description="最近一次实际探测端点可达的日期")


class MarketplaceInputError(ValueError):
    """缺少必填输入"""

    def __init__(self, missing: List[MarketplaceInput]):
        self.missing = [i.key for i in missing]
        labels = "、".join(i.label for i in missing)
        super().__init__(f"缺少必填项：{labels}")


@lru_cache(maxsize=1)
def load_catalog() -> List[MarketplaceItem]:
    with _CATALOG_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [MarketplaceItem(**entry) for entry in raw["items"]]


def get_item(item_id: str) -> Optional[MarketplaceItem]:
    return next((item for item in load_catalog() if item.id == item_id), None)


def find_placeholders(obj: Any) -> set:
    """递归收集字符串里的 {{KEY}} 占位符名"""
    if isinstance(obj, str):
        return set(_PLACEHOLDER.findall(obj))
    if isinstance(obj, dict):
        return set().union(*(find_placeholders(v) for v in obj.values())) if obj else set()
    if isinstance(obj, (list, tuple)):
        return set().union(*(find_placeholders(v) for v in obj)) if obj else set()
    return set()


def _substitute(text: str, values: Dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def render_server_config(item: MarketplaceItem, inputs: Dict[str, str]) -> Dict[str, Any]:
    """
    用用户输入渲染目录项，产出标准 mcpServers 片段（可直接交给 parse_server_config）。

    - 必填项缺失/空白 → MarketplaceInputError
    - 可选项为空 → 丢弃引用了它的 header（URL 中的占位符必须是必填，目录测试保证这一点）
    """
    declared = {i.key: i for i in item.inputs}
    values = {k: (inputs.get(k) or "").strip() for k in declared}

    missing = [declared[k] for k, v in values.items() if declared[k].required and not v]
    if missing:
        raise MarketplaceInputError(missing)

    empty_optional = {k for k, v in values.items() if not v}

    rendered: Dict[str, Any] = {
        "type": "sse" if item.transport == TRANSPORT_SSE else "http",
        "url": _substitute(str(item.server["url"]), values),
    }
    headers = {
        name: _substitute(str(value), values)
        for name, value in (item.server.get("headers") or {}).items()
        if not (find_placeholders(value) & empty_optional)
    }
    if headers:
        rendered["headers"] = headers
    return rendered


__all__ = [
    "CATEGORIES",
    "MarketplaceInput",
    "MarketplaceInputError",
    "MarketplaceItem",
    "TRANSPORT_SSE",
    "TRANSPORT_STREAMABLE_HTTP",
    "find_placeholders",
    "get_item",
    "load_catalog",
    "render_server_config",
]
