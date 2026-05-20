"""拆书 V3 R2 验收测试：_write_reference_pack + 编排器 import

只验证持久化层逻辑，不跑完整流水线（那是 R6 端到端的事）。

覆盖：
- 全部 5 维度成功 → status='ready'，无 error_message
- 部分维度成功 → status='partial'，error_message 列出缺失维度
- 全部失败 → status='failed'，error_message='全部维度生成失败'
- 重抽（已有 pack）→ upsert 更新而非创建（同一 task_id 始终对应一条记录）
- source_book_title 兜底（task.file_name 缺失时用'未命名拆书'）
- 编排器 import 正常，且废弃的 SynopsisGenerator 不再出现在 import 中
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import database  # noqa: F401  确保所有模型注册到 metadata
from app.db_base import Base
from app.models.book_dissect_task import BookDissectTask
from app.models.reference_pack import ReferencePack
from app.services.book_dissect.extractor_v2 import _write_reference_pack


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        await sess.close()
        await engine.dispose()


async def _make_task(session: AsyncSession, file_name: str | None = "原书.txt") -> BookDissectTask:
    task = BookDissectTask(
        id="task-1234567890",
        user_id="user-1",
        status="running",
        file_name=file_name,
        chapter_count=120,
        total_words=600000,
        version=2,
    )
    session.add(task)
    await session.flush()
    return task


def _full_payload() -> dict:
    """5 维度全部成功的 payload。"""
    return {
        "methodology": {"golden_finger_pattern": {"type": "传承流"}},
        "style": {"prompt_content": "你以..."},
        "structure": {"opening_pattern": {"hook_subtype": "灭门流"}},
        "archetypes": {"protagonist_archetype": {"introduction_pattern": "..."}},
        "worldbuilding": {"era_design": {"anchor_type": "修真大陆"}},
    }


# ============================================================
# 1. status 逻辑
# ============================================================


class TestStatusLogic:

    @pytest.mark.asyncio
    async def test_all_dims_ready(self, session):
        task = await _make_task(session)
        pack_id = await _write_reference_pack(
            db_session=session,
            task=task,
            payload=_full_payload(),
            generated_dims=["methodology", "style", "structure", "archetypes", "worldbuilding"],
        )
        await session.commit()

        result = await session.execute(select(ReferencePack).where(ReferencePack.id == pack_id))
        pack = result.scalar_one()
        assert pack.status == "ready"
        assert pack.error_message is None
        # 5 个 JSON 字段都写入
        assert pack.methodology_json is not None
        assert pack.style_json is not None
        assert pack.structure_json is not None
        assert pack.archetypes_json is not None
        assert pack.worldbuilding_json is not None
        # generated_dimensions JSON 数组
        dims = json.loads(pack.generated_dimensions)
        assert set(dims) == {"methodology", "style", "structure", "archetypes", "worldbuilding"}

    @pytest.mark.asyncio
    async def test_partial_dims(self, session):
        task = await _make_task(session)
        payload = {
            "methodology": {"x": 1},
            "style": {"prompt_content": "y"},
            "structure": None,
            "archetypes": None,
            "worldbuilding": None,
        }
        pack_id = await _write_reference_pack(
            db_session=session,
            task=task,
            payload=payload,
            generated_dims=["methodology", "style"],
        )
        await session.commit()
        result = await session.execute(select(ReferencePack).where(ReferencePack.id == pack_id))
        pack = result.scalar_one()
        assert pack.status == "partial"
        assert pack.error_message is not None
        assert "structure" in pack.error_message
        assert "archetypes" in pack.error_message
        assert "worldbuilding" in pack.error_message
        # 失败维度的 JSON 字段为 None
        assert pack.structure_json is None
        assert pack.archetypes_json is None
        assert pack.worldbuilding_json is None

    @pytest.mark.asyncio
    async def test_all_failed(self, session):
        task = await _make_task(session)
        payload = dict.fromkeys(
            ["methodology", "style", "structure", "archetypes", "worldbuilding"], None,
        )
        pack_id = await _write_reference_pack(
            db_session=session, task=task, payload=payload, generated_dims=[],
        )
        await session.commit()
        result = await session.execute(select(ReferencePack).where(ReferencePack.id == pack_id))
        pack = result.scalar_one()
        assert pack.status == "failed"
        # V3.2：status 判定仅看 5 个核心维度；synopsis 是可选增强不计入
        assert pack.error_message == "全部核心维度生成失败"


# ============================================================
# 2. upsert 行为
# ============================================================


class TestUpsert:

    @pytest.mark.asyncio
    async def test_re_extract_updates_in_place(self, session):
        """同一 task 重抽时应更新现有 pack，而不是创建新 pack。"""
        task = await _make_task(session)

        # 第一次：partial
        first_id = await _write_reference_pack(
            db_session=session, task=task,
            payload={"methodology": {"v": 1}, "style": None,
                     "structure": None, "archetypes": None, "worldbuilding": None},
            generated_dims=["methodology"],
        )
        await session.commit()

        # 第二次：完整（重抽成功）
        second_id = await _write_reference_pack(
            db_session=session, task=task,
            payload=_full_payload(),
            generated_dims=["methodology", "style", "structure", "archetypes", "worldbuilding"],
        )
        await session.commit()

        # ID 不变（同一记录被更新）
        assert first_id == second_id
        # 数据库只有一条
        result = await session.execute(select(ReferencePack).where(ReferencePack.task_id == task.id))
        all_packs = result.scalars().all()
        assert len(all_packs) == 1
        # 状态升级为 ready
        assert all_packs[0].status == "ready"
        assert all_packs[0].error_message is None


# ============================================================
# 3. source_book_title 兜底
# ============================================================


class TestSourceBookTitle:

    @pytest.mark.asyncio
    async def test_uses_task_file_name(self, session):
        task = await _make_task(session, file_name="斗破苍穹.txt")
        pack_id = await _write_reference_pack(
            db_session=session, task=task, payload=_full_payload(),
            generated_dims=["methodology", "style", "structure", "archetypes", "worldbuilding"],
        )
        await session.commit()
        result = await session.execute(select(ReferencePack).where(ReferencePack.id == pack_id))
        pack = result.scalar_one()
        assert pack.source_book_title == "斗破苍穹.txt"

    @pytest.mark.asyncio
    async def test_fallback_when_no_filename(self, session):
        task = await _make_task(session, file_name=None)
        pack_id = await _write_reference_pack(
            db_session=session, task=task, payload=_full_payload(),
            generated_dims=["methodology", "style", "structure", "archetypes", "worldbuilding"],
        )
        await session.commit()
        result = await session.execute(select(ReferencePack).where(ReferencePack.id == pack_id))
        pack = result.scalar_one()
        assert pack.source_book_title == "未命名拆书"


# ============================================================
# 4. 编排器 import：synopsis_generator 不再被引用
# ============================================================


class TestOrchestratorImport:

    def test_extractor_v2_imports_v3_generators(self):
        """编排器现在应 import V3 的 5 个 generator。"""
        import app.services.book_dissect.extractor_v2 as mod
        # V3 generator 已出现
        assert hasattr(mod, "MethodologyGenerator")
        assert hasattr(mod, "StyleGenerator")
        assert hasattr(mod, "StructureGenerator")
        assert hasattr(mod, "ArchetypeGenerator")
        assert hasattr(mod, "WorldbuildingGenerator")

    def test_extractor_v2_imports_synopsis_generator_v32(self):
        """V3.2：SynopsisGenerator 被复活，作为 Story Bible 层可选增强维度。

        V3 早期可能走入复刻原书内容的错误，被废弃；V3.2 重写为抽「类型骨架」
        （genre/premise/golden_finger/power_system 等抽象描述，禁出现具体专有名词）。
        详见：@/agent-docs/features/dissect_to_creation_pipeline.md §A.6
        """
        import app.services.book_dissect.extractor_v2 as mod
        # V3.2 应重新 import SynopsisGenerator
        assert hasattr(mod, "SynopsisGenerator"), \
            "V3.2 应复活 SynopsisGenerator，请检查 extractor_v2.py import"

    def test_write_reference_pack_helper_exposed(self):
        """_write_reference_pack 函数应在 extractor_v2 里可被引用（供测试和未来 API 复用）。"""
        from app.services.book_dissect.extractor_v2 import _write_reference_pack
        assert callable(_write_reference_pack)
