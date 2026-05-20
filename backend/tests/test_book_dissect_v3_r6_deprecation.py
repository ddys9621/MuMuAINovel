"""V3 R6 验收测试：apply_to_wizard 已废弃路径

策略与 R3 / R5 一致：构造最小 FastAPI app 仅注册 book_dissect router，
覆盖 require_login + get_db。

覆盖：
- POST /api/book-dissect/{task_id}/apply-to-wizard 返 410 Gone
- 错误体含 code / message / migration / new_endpoints 字段
- 即使任务不存在 / 任务未完成，也一律 410（路径已废弃，不再做业务校验）
- apply_service / ApplyToWizardRequest 等模块已彻底移除
"""

from __future__ import annotations

import importlib
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import database  # noqa: F401  注册所有模型
from app.api import book_dissect as bd_api
from app.api.users import require_login
from app.database import get_db
from app.db_base import Base
from app.models.book_dissect_task import BookDissectTask
from app.user_manager import User


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _make_user(uid: str = "user-A") -> User:
    return User(
        user_id=uid,
        username=uid,
        display_name=uid,
        avatar_url=None,
        trust_level=1,
        is_admin=False,
        linuxdo_id=uid,
        created_at=datetime.now().isoformat(),
        last_login=datetime.now().isoformat(),
    )


def _build_app(session_factory, current_user: User) -> FastAPI:
    """仅注册 book_dissect router，并覆盖 require_login / get_db。"""
    app = FastAPI()
    app.include_router(bd_api.router, prefix="/api")

    async def _override_get_db():
        sess = session_factory()
        try:
            yield sess
        finally:
            await sess.close()

    def _override_require_login():
        return current_user

    app.dependency_overrides[get_db] = _override_get_db
    # book_dissect.py 在模块内自定义了 require_login（不是从 app.api.users 导入）
    app.dependency_overrides[bd_api.require_login] = _override_require_login
    return app


# ============================================================
# 1) 端点行为
# ============================================================


class TestApplyToWizardDeprecated:
    @pytest.mark.asyncio
    async def test_returns_410_with_migration_payload(self, session_factory):
        """对一个真实存在的 completed 任务也直接返 410。"""
        async with session_factory() as sess:
            task = BookDissectTask(
                id="t-1", user_id="user-A", status="completed",
                file_name="x.txt", chapter_count=10, total_words=10000,
                version=2,
            )
            sess.add(task)
            await sess.commit()

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/book-dissect/t-1/apply-to-wizard",
                json={"fields_to_apply": ["project"]},
            )
            assert resp.status_code == 410
            body = resp.json()
            detail = body["detail"]
            assert detail["code"] == "apply_to_wizard_deprecated"
            assert "已废弃" in detail["message"]
            assert isinstance(detail["migration"], list) and len(detail["migration"]) >= 3
            assert any("一键仿写" in step for step in detail["migration"])
            # 新端点指引
            assert any("imitate-chapter-stream" in ep for ep in detail["new_endpoints"])

    @pytest.mark.asyncio
    async def test_returns_410_even_for_unknown_task(self, session_factory):
        """端点已废弃，连任务存在性都不再校验。"""
        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/book-dissect/non-existent/apply-to-wizard",
                json={},
            )
            assert resp.status_code == 410
            assert resp.json()["detail"]["code"] == "apply_to_wizard_deprecated"

    @pytest.mark.asyncio
    async def test_returns_410_for_running_task(self, session_factory):
        """即使任务还在跑，也直接 410，而不是历史上的 409。"""
        async with session_factory() as sess:
            task = BookDissectTask(
                id="t-running", user_id="user-A", status="running",
                file_name="x.txt", chapter_count=10, total_words=10000,
                version=2,
            )
            sess.add(task)
            await sess.commit()

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/book-dissect/t-running/apply-to-wizard",
                json={},
            )
            assert resp.status_code == 410

    @pytest.mark.asyncio
    async def test_endpoint_is_marked_deprecated_in_openapi(self, session_factory):
        """OpenAPI schema 应当把该端点标 deprecated=True。"""
        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/openapi.json")
            assert resp.status_code == 200
            schema = resp.json()
        path = schema["paths"]["/api/book-dissect/{task_id}/apply-to-wizard"]
        op = path["post"]
        assert op.get("deprecated") is True
        # 410 status code 在 responses 中
        assert "410" in op["responses"] or "default" in op["responses"]


# ============================================================
# 2) 死代码移除
# ============================================================


class TestDeadCodeRemoved:
    def test_apply_service_module_removed(self):
        """apply_service.py 已删除：import 必须失败。"""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.services.book_dissect.apply_service")

    def test_apply_to_wizard_request_removed(self):
        """ApplyToWizardRequest / Response 已从 schema 中移除。"""
        from app.schemas import book_dissect as bd_schema

        assert not hasattr(bd_schema, "ApplyToWizardRequest")
        assert not hasattr(bd_schema, "ApplyToWizardResponse")
