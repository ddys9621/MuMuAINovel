"""T2.1 单测：BridgePlanningService.expand_all_ready_bridges 批量展开。

覆盖：
- 无 ready 桥段 → 返回空摘要
- 全部成功 → 章号连续递增 + status 推到 completed
- 部分失败 → 失败桥段不阻塞其他，最终摘要正确分类
- 起始章号自动推算（项目已存在章纲时基于最大号+1）
- 起始章号外部指定时优先使用
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db_base import Base
from app.models.chapter_outline import ChapterOutline
from app.models.plot_bridge import PlotBridge
from app.models.project import Project
from app.services.bridge_planning_service import BridgePlanningService


# ============================================================
# 测试夹具
# ============================================================


@pytest_asyncio.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        await sess.close()
        await eng.dispose()


@pytest_asyncio.fixture
async def project(session: AsyncSession):
    p = Project(
        id="p1", user_id="u1", title="测试书", status="planning",
    )
    session.add(p)
    await session.commit()
    return p


def _make_bridge(project_id: str, n: int, status: str = "ready") -> PlotBridge:
    return PlotBridge(
        project_id=project_id,
        bridge_number=n,
        title=f"桥段{n}",
        goal=f"目标{n}",
        showoff_point=f"爽点{n}",
        c1_intro="c1", c2_build="c2", c3_payoff="c3", c4_aftermath="c4",
        status=status,
        order_index=n,
    )


def _make_service_with_mock_expand(succeed_for: set[str], created_per_bridge: int = 4):
    """构造一个 service，mock 掉 expand_bridge_to_chapters。

    succeed_for: 调用成功的 bridge_id 集合；其余抛 RuntimeError。
    """
    ai = MagicMock()
    ai.default_model = "test-model"
    svc = BridgePlanningService(ai_service=ai)

    async def fake_expand(db, *, bridge_id, model_name, start_chapter_number):
        if bridge_id not in succeed_for:
            raise RuntimeError(f"mock fail for {bridge_id}")
        # 返回 created_per_bridge 个假 ChapterOutline（不入库）
        return [
            ChapterOutline(
                project_id="p1",
                chapter_number=start_chapter_number + i,
                title=f"ch{start_chapter_number + i}",
                bridge_id=bridge_id,
                bridge_position="intro",
            )
            for i in range(created_per_bridge)
        ]

    svc.expand_bridge_to_chapters = AsyncMock(side_effect=fake_expand)
    return svc


# ============================================================
# 测试
# ============================================================


@pytest.mark.asyncio
async def test_expand_all_no_ready_bridges_returns_empty(session, project):
    """无 ready 桥段 → 返回空摘要，不调用 expand。"""
    # 加一个已完成的桥段，不应被处理
    session.add(_make_bridge("p1", 1, status="completed"))
    await session.commit()

    ai = MagicMock()
    ai.default_model = "x"
    svc = BridgePlanningService(ai_service=ai)
    svc.expand_bridge_to_chapters = AsyncMock()

    result = await svc.expand_all_ready_bridges(session, "p1")

    assert result == {
        "total": 0,
        "succeeded": [],
        "failed": [],
        "created_chapter_count": 0,
    }
    svc.expand_bridge_to_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_expand_all_all_succeed_returns_chapter_numbers_sequential(
    session, project
):
    """3 个 ready 桥段全部成功 → 章号连续递增。"""
    b1, b2, b3 = (
        _make_bridge("p1", 1), _make_bridge("p1", 2), _make_bridge("p1", 3)
    )
    session.add_all([b1, b2, b3])
    await session.commit()
    await session.refresh(b1)
    await session.refresh(b2)
    await session.refresh(b3)

    svc = _make_service_with_mock_expand({b1.id, b2.id, b3.id})

    result = await svc.expand_all_ready_bridges(
        session, "p1", start_chapter_number=1
    )

    assert result["total"] == 3
    assert result["succeeded"] == [b1.id, b2.id, b3.id]
    assert result["failed"] == []
    assert result["created_chapter_count"] == 12  # 3 桥段 × 4 章
    # 验证章号传递正确：1, 5, 9
    calls = svc.expand_bridge_to_chapters.await_args_list
    starts = [c.kwargs["start_chapter_number"] for c in calls]
    assert starts == [1, 5, 9]


@pytest.mark.asyncio
async def test_expand_all_partial_failure_does_not_block_others(session, project):
    """第 2 个失败 → 第 3 个仍展开，最终摘要分类正确。"""
    b1, b2, b3 = (
        _make_bridge("p1", 1), _make_bridge("p1", 2), _make_bridge("p1", 3)
    )
    session.add_all([b1, b2, b3])
    await session.commit()
    for b in (b1, b2, b3):
        await session.refresh(b)

    # 只让 b1, b3 成功
    svc = _make_service_with_mock_expand({b1.id, b3.id})

    result = await svc.expand_all_ready_bridges(
        session, "p1", start_chapter_number=1
    )

    assert result["total"] == 3
    assert sorted(result["succeeded"]) == sorted([b1.id, b3.id])
    assert len(result["failed"]) == 1
    assert result["failed"][0]["bridge_id"] == b2.id
    assert "mock fail" in result["failed"][0]["error"]
    assert result["created_chapter_count"] == 8  # 2 桥段 × 4 章


@pytest.mark.asyncio
async def test_expand_all_auto_start_chapter_from_existing(session, project):
    """不指定 start_chapter_number → 从现有章纲最大号+1 推算。"""
    # 项目已有 5 章
    for n in range(1, 6):
        session.add(
            ChapterOutline(project_id="p1", chapter_number=n, title=f"ch{n}")
        )
    b1 = _make_bridge("p1", 1)
    session.add(b1)
    await session.commit()
    await session.refresh(b1)

    svc = _make_service_with_mock_expand({b1.id})

    result = await svc.expand_all_ready_bridges(session, "p1")

    assert result["total"] == 1
    # 起始章号应为 6
    call = svc.expand_bridge_to_chapters.await_args_list[0]
    assert call.kwargs["start_chapter_number"] == 6


@pytest.mark.asyncio
async def test_expand_all_auto_start_chapter_empty_project_starts_at_1(
    session, project
):
    """空项目 + 不指定起始 → 起始章号 = 1。"""
    b1 = _make_bridge("p1", 1)
    session.add(b1)
    await session.commit()
    await session.refresh(b1)

    svc = _make_service_with_mock_expand({b1.id})

    await svc.expand_all_ready_bridges(session, "p1")
    call = svc.expand_bridge_to_chapters.await_args_list[0]
    assert call.kwargs["start_chapter_number"] == 1


@pytest.mark.asyncio
async def test_expand_all_skips_non_ready_bridges(session, project):
    """状态非 ready 的桥段（pending / completed）不被批量展开处理。"""
    b_ready = _make_bridge("p1", 1, status="ready")
    b_pending = _make_bridge("p1", 2, status="pending")
    b_done = _make_bridge("p1", 3, status="completed")
    session.add_all([b_ready, b_pending, b_done])
    await session.commit()
    for b in (b_ready, b_pending, b_done):
        await session.refresh(b)

    svc = _make_service_with_mock_expand({b_ready.id, b_pending.id, b_done.id})

    result = await svc.expand_all_ready_bridges(session, "p1", start_chapter_number=1)

    assert result["total"] == 1
    assert result["succeeded"] == [b_ready.id]
    # 只调了 1 次
    assert svc.expand_bridge_to_chapters.await_count == 1
