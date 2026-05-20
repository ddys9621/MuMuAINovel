"""拆书 V3 R3 验收测试：参考包 API + 项目挂载 API

策略：
- 不启动整个 FastAPI app，避免引入鉴权中间件和无关 router 的副作用
- 构造一个最小 app 只注册 reference_pack 的两个 router
- 用 dependency_overrides 替换 require_login（提供测试用户）和 get_db（提供内存 DB）

覆盖：
- 参考包列表 / 详情 / 删除
- 项目挂载 / 卸载 / 列表 / 配置更新
- 跨用户隔离（A 看不到 B 的 pack）
- 重复挂载 409
- 挂载未就绪 pack 409
- attached_count 准确
- default_dimensions 推断（只保留生成成功的维度 + corpus）
- 状态映射：generating / ready / partial / failed
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import database  # noqa: F401  注册所有模型
from app.api import reference_pack as ref_api
from app.database import get_db
from app.db_base import Base
from app.models.book_dissect_task import BookDissectTask
from app.models.project import Project
from app.models.project_reference_pack import ProjectReferencePack
from app.models.reference_pack import ReferencePack
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


def _build_app(session_factory, current_user: User) -> FastAPI:
    """构造仅含 V3 reference_pack 路由的最小 app + 依赖覆盖。"""
    app = FastAPI()
    app.include_router(ref_api.router, prefix="/api")
    app.include_router(ref_api.project_router, prefix="/api")

    async def _override_get_db():
        sess = session_factory()
        try:
            yield sess
        finally:
            await sess.close()

    def _override_require_login():
        return current_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[ref_api.require_login] = _override_require_login
    return app


def _make_user(uid: str = "user-A") -> User:
    return User(
        user_id=uid, username=uid, display_name=uid,
        avatar_url=None, trust_level=1, is_admin=False,
        linuxdo_id=uid,
        created_at=datetime.now().isoformat(),
        last_login=datetime.now().isoformat(),
    )


async def _seed_task_and_pack(
    session: AsyncSession,
    user_id: str,
    task_id: str,
    pack_status: str = "ready",
    generated_dims: list[str] | None = None,
    book_title: str = "测试书.txt",
) -> tuple[BookDissectTask, ReferencePack]:
    task = BookDissectTask(
        id=task_id, user_id=user_id, status="completed",
        file_name=book_title, chapter_count=120, total_words=600000,
        version=2,
    )
    session.add(task)
    await session.flush()

    if generated_dims is None:
        generated_dims = ["methodology", "style", "structure", "archetypes", "worldbuilding"]

    pack = ReferencePack(
        user_id=user_id,
        task_id=task.id,
        source_book_title=book_title,
        methodology_json=json.dumps({"v": "methodology"}, ensure_ascii=False)
            if "methodology" in generated_dims else None,
        style_json=json.dumps({"prompt_content": "..."}) if "style" in generated_dims else None,
        structure_json=json.dumps({"v": "structure"}) if "structure" in generated_dims else None,
        archetypes_json=json.dumps({"v": "archetypes"}) if "archetypes" in generated_dims else None,
        worldbuilding_json=json.dumps({"v": "worldbuilding"}) if "worldbuilding" in generated_dims else None,
        status=pack_status,
        generated_dimensions=json.dumps(generated_dims, ensure_ascii=False),
    )
    session.add(pack)
    await session.flush()
    return task, pack


async def _seed_project(session: AsyncSession, user_id: str, project_id: str = "proj-1") -> Project:
    proj = Project(
        id=project_id, user_id=user_id, title="测试项目",
        description="", target_words=100000, status="planning",
        wizard_status="incomplete", wizard_step=0,
    )
    session.add(proj)
    await session.flush()
    return proj


# ============================================================
# 1. 参考包：列表 / 详情 / 删除
# ============================================================


class TestReferencePackCRUD:

    @pytest.mark.asyncio
    async def test_list_returns_user_packs_only(self, session_factory):
        """跨用户隔离：A 不应看到 B 的 pack。"""
        async with session_factory() as sess:
            await _seed_task_and_pack(sess, "user-A", "task-A1")
            await _seed_task_and_pack(sess, "user-B", "task-B1")
            await sess.commit()

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/reference-packs")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["user_id"] == "user-A"
            assert data[0]["status"] == "ready"
            assert data[0]["attached_project_count"] == 0
            assert "methodology" in data[0]["generated_dimensions"]

    @pytest.mark.asyncio
    async def test_get_detail_includes_5_tabs(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/reference-packs/{pack_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["methodology"] == {"v": "methodology"}
            assert data["style"] == {"prompt_content": "..."}
            assert data["structure"] == {"v": "structure"}
            assert data["archetypes"] == {"v": "archetypes"}
            assert data["worldbuilding"] == {"v": "worldbuilding"}

    @pytest.mark.asyncio
    async def test_get_detail_404_for_other_user(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-B", "task-B")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/reference-packs/{pack_id}")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_pack_cascades_attachments(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-X")
            sess.add(ProjectReferencePack(
                project_id="proj-X", pack_id=pack.id,
                default_dimensions=json.dumps(["methodology"]),
                default_strength="medium",
            ))
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/reference-packs/{pack_id}")
            assert resp.status_code == 200

        async with session_factory() as sess:
            from sqlalchemy import select
            r = await sess.execute(select(ReferencePack).where(ReferencePack.id == pack_id))
            assert r.scalar_one_or_none() is None
            r2 = await sess.execute(select(ProjectReferencePack).where(ProjectReferencePack.pack_id == pack_id))
            assert r2.scalar_one_or_none() is None  # CASCADE


# ============================================================
# 2. 项目挂载：挂载 / 列表 / 配置 / 卸载
# ============================================================


class TestProjectAttach:

    @pytest.mark.asyncio
    async def test_attach_basic(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["pack_id"] == pack_id
            assert data["default_strength"] == "medium"
            # 默认推断 medium = methodology + style + corpus
            assert set(data["default_dimensions"]) == {"methodology", "style", "corpus"}

    @pytest.mark.asyncio
    async def test_attach_explicit_dimensions(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/reference-packs",
                json={
                    "pack_id": pack_id,
                    "default_dimensions": ["style", "corpus"],
                    "default_strength": "light",
                },
            )
            assert resp.status_code == 200
            assert set(resp.json()["default_dimensions"]) == {"style", "corpus"}

    @pytest.mark.asyncio
    async def test_attach_filters_invalid_dimensions(self, session_factory):
        """挂载时只保留参考包真实生成的维度 + corpus。"""
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(
                sess, "user-A", "task-1",
                pack_status="partial",
                generated_dims=["methodology", "style"],  # 只生成了 2 维度
            )
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/reference-packs",
                json={
                    "pack_id": pack_id,
                    # 用户请求 deep（全部 6 维度），但参考包只生成了 methodology+style
                    "default_strength": "deep",
                },
            )
            assert resp.status_code == 200
            dims = set(resp.json()["default_dimensions"])
            # structure / archetypes / worldbuilding 被过滤掉，corpus 保留
            assert dims == {"methodology", "style", "corpus"}

    @pytest.mark.asyncio
    async def test_attach_409_when_pack_not_ready(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(
                sess, "user-A", "task-1",
                pack_status="generating",
                generated_dims=[],
            )
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            assert resp.status_code == 409
            assert "未就绪" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_attach_409_on_duplicate(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            assert r1.status_code == 200
            r2 = await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            assert r2.status_code == 409
            assert "已挂载" in r2.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_attachments(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            resp = await client.get("/api/projects/proj-1/reference-packs")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["pack_id"] == pack_id
            assert data[0]["pack_summary"]["source_book_title"] == "测试书.txt"
            assert data[0]["pack_summary"]["attached_project_count"] == 1

    @pytest.mark.asyncio
    async def test_patch_attachment(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            r = await client.patch(
                f"/api/projects/proj-1/reference-packs/{pack_id}",
                json={"default_strength": "deep", "default_dimensions": ["methodology", "structure"]},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["default_strength"] == "deep"
            assert set(data["default_dimensions"]) == {"methodology", "structure"}

    @pytest.mark.asyncio
    async def test_detach(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            r = await client.delete(f"/api/projects/proj-1/reference-packs/{pack_id}")
            assert r.status_code == 200

            # 二次卸载 404
            r2 = await client.delete(f"/api/projects/proj-1/reference-packs/{pack_id}")
            assert r2.status_code == 404

    @pytest.mark.asyncio
    async def test_attach_to_other_users_project_404(self, session_factory):
        """不能把自己的 pack 挂到别人的项目（项目不属于自己）。"""
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-B", "proj-other")  # 项目属于 B
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-other/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            assert resp.status_code == 404


# ============================================================
# 3. attached_count 准确性
# ============================================================


class TestAttachedCount:

    @pytest.mark.asyncio
    async def test_count_increments_on_attach(self, session_factory):
        async with session_factory() as sess:
            _, pack = await _seed_task_and_pack(sess, "user-A", "task-1")
            await _seed_project(sess, "user-A", "proj-1")
            await _seed_project(sess, "user-A", "proj-2")
            await sess.commit()
            pack_id = pack.id

        app = _build_app(session_factory, _make_user("user-A"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 初始 0
            r = await client.get(f"/api/reference-packs/{pack_id}")
            assert r.json()["attached_project_count"] == 0
            # 挂到 proj-1
            await client.post(
                "/api/projects/proj-1/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            r = await client.get(f"/api/reference-packs/{pack_id}")
            assert r.json()["attached_project_count"] == 1
            # 挂到 proj-2
            await client.post(
                "/api/projects/proj-2/reference-packs",
                json={"pack_id": pack_id, "default_strength": "medium"},
            )
            r = await client.get(f"/api/reference-packs/{pack_id}")
            assert r.json()["attached_project_count"] == 2
            # 列表也是 2
            r = await client.get("/api/reference-packs")
            assert r.json()[0]["attached_project_count"] == 2
