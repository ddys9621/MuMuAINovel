"""阶段 3 单测：BridgePlanningService.expand_bridge_to_chapters 升级后行为验证。

新增能力：
- 流式累积调用（generate_text_stream_collect 取代 generate_text）
- 每个章纲同步入库 3-5 张 PlotCard + PlotCardChapterOutlineLink（与原路径对等）

向后兼容性：
- scenes 字段缺失 / 非 list / 元素非 dict / 元素缺 title → 该位置跳过卡片，但章纲仍入库
- 老 LLM prompt 路径（不知道 scenes 字段）不会因为本次升级失效
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db_base import Base
from app.models.chapter_outline import ChapterOutline
from app.models.plot_bridge import PlotBridge
from app.models.plot_card import PlotCard
from app.models.plot_card_chapter_outline_link import PlotCardChapterOutlineLink
from app.models.project import Project
from app.services.bridge_planning_service import BridgePlanningService
from app.services.reference_pack import AssembledPrompt


# ============================================================
# Fixtures
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
    p = Project(id="p-exp", user_id="u1", title="测试书", status="planning")
    session.add(p)
    await session.commit()
    return p


@pytest_asyncio.fixture
async def bridge(session: AsyncSession, project: Project):
    b = PlotBridge(
        id="b-exp",
        project_id="p-exp",
        bridge_number=1,
        title="桥段：拜入青云宗",
        goal="主角拜入门派",
        showoff_point="灵根测试爆表",
        c1_intro="测试 C1", c2_build="测试 C2", c3_payoff="测试 C3", c4_aftermath="测试 C4",
        status="ready",
        order_index=1,
    )
    session.add(b)
    await session.commit()
    return b


def _make_assembled_prompt() -> AssembledPrompt:
    return AssembledPrompt(
        system_prompt="test sys",
        user_prompt="test user",
        user_blocks=[],
        slots_filled=["synopsis", "methodology"],
        slots_truncated=[],
        slots_skipped=[],
        actual_tokens_estimate=1000,
    )


def _make_service(stream_collect_return=None, stream_collect_exc=None):
    ai = MagicMock()
    ai.default_model = "default-test-model"
    if stream_collect_exc:
        ai.generate_text_stream_collect = AsyncMock(side_effect=stream_collect_exc)
    else:
        ai.generate_text_stream_collect = AsyncMock(return_value=stream_collect_return)

    svc = BridgePlanningService(ai_service=ai)
    svc.assembler = MagicMock()
    svc.assembler.assemble = AsyncMock(return_value=_make_assembled_prompt())
    return svc, ai


def _chapter(num: int, position: str, scenes: list | None = None) -> dict:
    obj = {
        "chapter_number": num,
        "title": f"第{num}章 {position}",
        "bridge_position": position,
        "scene": "青云山",
        "pov": "主角",
        "plot_points": f"本章 {position} 剧情",
        "key_events": [f"事件{num}-1", f"事件{num}-2"],
        "characters_involved": ["主角", "门派长老"],
        "target_word_count": 3000,
    }
    if scenes is not None:
        obj["scenes"] = scenes
    return obj


def _scene(idx: int, card_type: str = "scene") -> dict:
    return {
        "title": f"场景 {idx + 1}",
        "content": f"场景 {idx + 1} 的内容描述",
        "card_type": card_type,
        "scene_order": idx,
        "word_count_target": 500 + idx * 50,
    }


# ============================================================
# Tests
# ============================================================


@pytest.mark.asyncio
async def test_expand_creates_4_chapters_and_scenes(session, bridge):
    """完整路径：4 章 + 每章 3 张卡片，PlotCard + Link 全部入库。"""
    chapters_json = json.dumps([
        _chapter(1, "intro", scenes=[_scene(0, "inner"), _scene(1, "scene"), _scene(2, "dialogue")]),
        _chapter(2, "build", scenes=[_scene(0, "scene"), _scene(1, "conflict"), _scene(2, "event")]),
        _chapter(3, "payoff", scenes=[_scene(0), _scene(1), _scene(2), _scene(3), _scene(4)]),
        _chapter(4, "aftermath", scenes=[_scene(0), _scene(1, "event")]),
    ])
    svc, ai = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )

    created = await svc.expand_bridge_to_chapters(
        session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
    )

    # 章纲
    assert len(created) == 4
    assert [c.bridge_position for c in created] == ["intro", "build", "payoff", "aftermath"]
    assert all(c.bridge_id == "b-exp" for c in created)

    # 桥段 status 推进
    bridge_after = (await session.execute(
        select(PlotBridge).where(PlotBridge.id == "b-exp")
    )).scalar_one()
    assert bridge_after.status == "completed"

    # 卡片入库（3 + 3 + 5 + 2 = 13 张）
    cards = (await session.execute(select(PlotCard))).scalars().all()
    assert len(cards) == 13
    assert all(c.project_id == "p-exp" for c in cards)
    assert all(c.chapter_outline_id is not None for c in cards)
    # 第一张卡片是 inner 类型
    intro_chapter_id = next(c.id for c in created if c.bridge_position == "intro")
    intro_cards = sorted(
        [c for c in cards if c.chapter_outline_id == intro_chapter_id],
        key=lambda x: x.order_index or 0,
    )
    assert len(intro_cards) == 3
    assert intro_cards[0].card_type == "inner"

    # Link 全部入库，usage_type=planned
    links = (await session.execute(select(PlotCardChapterOutlineLink))).scalars().all()
    assert len(links) == 13
    assert all(link.usage_type == "planned" for link in links)


@pytest.mark.asyncio
async def test_expand_uses_stream_collect_not_generate_text(session, bridge):
    """关键不变量：必须走 generate_text_stream_collect。"""
    chapters_json = json.dumps([
        _chapter(1, "intro"), _chapter(2, "build"),
        _chapter(3, "payoff"), _chapter(4, "aftermath"),
    ])
    svc, ai = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )
    ai.generate_text = AsyncMock()

    await svc.expand_bridge_to_chapters(
        session, bridge_id="b-exp", model_name="claude-opus-4-7", start_chapter_number=1,
    )

    ai.generate_text_stream_collect.assert_awaited_once()
    ai.generate_text.assert_not_awaited()

    call_kwargs = ai.generate_text_stream_collect.await_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-7"
    assert call_kwargs["max_tokens"] == 8000  # 升级后从 4000 → 8000
    assert "BridgeExpansion" in call_kwargs["context"]


@pytest.mark.asyncio
async def test_expand_without_scenes_creates_only_chapters(session, bridge):
    """向后兼容：老 prompt 路径没有 scenes 字段 → 只入库章纲，PlotCard 表为空。"""
    chapters_json = json.dumps([
        _chapter(1, "intro"), _chapter(2, "build"),
        _chapter(3, "payoff"), _chapter(4, "aftermath"),
    ])
    svc, _ = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )

    created = await svc.expand_bridge_to_chapters(
        session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
    )

    assert len(created) == 4
    cards = (await session.execute(select(PlotCard))).scalars().all()
    assert cards == []
    links = (await session.execute(select(PlotCardChapterOutlineLink))).scalars().all()
    assert links == []


@pytest.mark.asyncio
async def test_expand_skips_non_list_scenes(session, bridge):
    """容错：scenes 不是 list（如字符串 / dict）→ 跳过该章的卡片入库，但章纲入库。"""
    chapters_json = json.dumps([
        {**_chapter(1, "intro"), "scenes": "not a list"},
        {**_chapter(2, "build"), "scenes": {"key": "value"}},  # dict 不是 list
        _chapter(3, "payoff", scenes=[_scene(0)]),  # 正常的有 1 张
        _chapter(4, "aftermath"),  # 缺 scenes
    ])
    svc, _ = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )

    created = await svc.expand_bridge_to_chapters(
        session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
    )
    assert len(created) == 4

    cards = (await session.execute(select(PlotCard))).scalars().all()
    assert len(cards) == 1  # 只有 payoff 章的 1 张卡


@pytest.mark.asyncio
async def test_expand_skips_invalid_scene_items(session, bridge):
    """容错：scenes 里的元素非 dict 或缺 title → 跳过该项。"""
    chapters_json = json.dumps([
        {**_chapter(1, "intro"), "scenes": [
            _scene(0),  # 合法
            "noise",  # 非 dict
            {"content": "缺 title"},  # 缺 title
            None,
            _scene(1, "dialogue"),  # 合法
        ]},
        _chapter(2, "build"),
        _chapter(3, "payoff"),
        _chapter(4, "aftermath"),
    ])
    svc, _ = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )

    await svc.expand_bridge_to_chapters(
        session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
    )

    cards = (await session.execute(select(PlotCard))).scalars().all()
    assert len(cards) == 2
    assert {c.card_type for c in cards} == {"scene", "dialogue"}


@pytest.mark.asyncio
async def test_expand_caps_scenes_at_8_per_chapter(session, bridge):
    """容错：单章超过 8 张卡片 → 只入库前 8，与原路径上限一致。"""
    chapters_json = json.dumps([
        {**_chapter(1, "intro"), "scenes": [_scene(i) for i in range(15)]},  # 15 张
        _chapter(2, "build"),
        _chapter(3, "payoff"),
        _chapter(4, "aftermath"),
    ])
    svc, _ = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )

    await svc.expand_bridge_to_chapters(
        session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
    )

    cards = (await session.execute(select(PlotCard))).scalars().all()
    assert len(cards) == 8


@pytest.mark.asyncio
async def test_expand_propagates_underlying_exception(session, bridge):
    """流式底层抛异常 → service 应原样抛出。"""
    import httpx

    svc, _ = _make_service(stream_collect_exc=httpx.ReadTimeout("network down"))

    with pytest.raises(httpx.ReadTimeout, match="network down"):
        await svc.expand_bridge_to_chapters(
            session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
        )


@pytest.mark.asyncio
async def test_expand_raises_when_less_than_4_chapters(session, bridge):
    """LLM 返回少于 4 章 → ValueError。"""
    chapters_json = json.dumps([_chapter(1, "intro"), _chapter(2, "build")])  # 只有 2 章
    svc, _ = _make_service(
        stream_collect_return={"content": chapters_json, "finish_reason": "stream_complete"}
    )

    with pytest.raises(ValueError, match="章纲少于 4 个|格式错误"):
        await svc.expand_bridge_to_chapters(
            session, bridge_id="b-exp", model_name=None, start_chapter_number=1,
        )


@pytest.mark.asyncio
async def test_expand_raises_when_bridge_not_found(session, project):
    """桥段不存在 → ValueError。"""
    svc, _ = _make_service(
        stream_collect_return={"content": "[]", "finish_reason": "stream_complete"}
    )

    with pytest.raises(ValueError, match="桥段不存在"):
        await svc.expand_bridge_to_chapters(
            session, bridge_id="nonexistent", model_name=None, start_chapter_number=1,
        )
