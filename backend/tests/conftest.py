"""测试公共 fixtures — 预先 mock 重度依赖以避免 import 报错"""
import os
import sys
import uuid
import asyncio
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ["DEBUG"] = "false"

# 在导入 app 模块之前，先 mock 掉 chromadb 及其子模块
# 这样 chapters.py → memory_service → chromadb 的导入链就不会炸
_HEAVY_DEPS = [
    "chromadb", "chromadb.config", "chromadb.api", "chromadb.api.types",
    "chromadb.auth", "chromadb.auth.token_authn",
    "chromadb.telemetry", "chromadb.telemetry.opentelemetry",
]
for mod in _HEAVY_DEPS:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def make_outline_mock(project_id: str, number: int, title: str | None = None):
    o = MagicMock()
    o.id = str(uuid.uuid4())
    o.project_id = project_id
    o.chapter_number = number
    o.title = title or f"第{number}章纲"
    o.summary = f"第{number}章摘要"
    return o
