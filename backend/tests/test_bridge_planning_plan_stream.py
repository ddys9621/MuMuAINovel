"""阶段 2 单测：BridgePlanningService.plan_bridges 改流式后行为验证。

覆盖：
- 流式累积成功 → JSON 解析正确 → 入库 N 个桥段（含 status=ready / order_index）
- 流式累积成功但 JSON 是空数组 → 抛 ValueError
- 流式累积成功但 JSON 非数组（dict / null） → 抛 ValueError
- 流式底层抛异常（模拟 ReadTimeout 持续失败）→ service 抛同异常
- 调用流式 helper 时透传了正确的 model / temperature / max_tokens / context
- 调用流式 helper 时 effective_model 回退到 ai_service.default_model
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db_base import Base
from app.models.plot_bridge import PlotBridge
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
    p = Project(id="p-stream", user_id="u1", title="测试书", status="planning")
    session.add(p)
    await session.commit()
    return p


def _make_assembled_prompt() -> AssembledPrompt:
    """构造一个最小可用的 AssembledPrompt，绕过真实拆书包装配。"""
    return AssembledPrompt(
        system_prompt="测试系统提示词",
        user_prompt="测试用户提示词",
        user_blocks=[],
        slots_filled=["synopsis", "methodology", "bridges"],
        slots_truncated=[],
        slots_skipped=[],
        actual_tokens_estimate=1234,
    )


def _make_service(stream_collect_return=None, stream_collect_exc=None):
    """构造 service，mock 掉 ai_service.generate_text_stream_collect + assembler。"""
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


def _sample_bridge_json(n: int = 3) -> str:
    return json.dumps(
        [
            {
                "bridge_number": i + 1,
                "title": f"桥段{i + 1}",
                "goal": f"目标{i + 1}",
                "showoff_point": f"装逼点{i + 1}",
                "golden_finger_usage": f"金手指{i + 1}",
                "c1_intro": f"C1 卡片{i + 1}",
                "c2_build": f"C2 卡片{i + 1}",
                "c3_payoff": f"C3 卡片{i + 1}",
                "c4_aftermath": f"C4 卡片{i + 1}",
                "next_bridge_hook": f"下钩{i + 1}",
            }
            for i in range(n)
        ],
        ensure_ascii=False,
    )


# ============================================================
# Tests
# ============================================================


@pytest.mark.asyncio
async def test_plan_bridges_stream_success_creates_n_bridges(session, project):
    """流式累积成功 → JSON 解析 → 入库 N 个桥段，全 status=ready，order_index 递增。"""
    svc, ai = _make_service(
        stream_collect_return={"content": _sample_bridge_json(3), "finish_reason": "stream_complete"}
    )

    created = await svc.plan_bridges(session, project_id="p-stream", bridge_count=3)

    assert len(created) == 3
    assert all(b.status == "ready" for b in created)
    assert [b.order_index for b in created] == [1, 2, 3]
    assert [b.bridge_number for b in created] == [1, 2, 3]
    assert [b.title for b in created] == ["桥段1", "桥段2", "桥段3"]

    # DB 校验：3 个桥段真的入库
    rows = (await session.execute(select(PlotBridge))).scalars().all()
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_plan_bridges_uses_stream_collect_not_generate_text(session, project):
    """关键不变量：必须走 generate_text_stream_collect，不走老的 generate_text。"""
    svc, ai = _make_service(
        stream_collect_return={"content": _sample_bridge_json(1), "finish_reason": "stream_complete"}
    )
    # 给老接口也加一个 mock，验证它没被调到
    ai.generate_text = AsyncMock()

    await svc.plan_bridges(session, project_id="p-stream", bridge_count=1)

    ai.generate_text_stream_collect.assert_awaited_once()
    ai.generate_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_plan_bridges_stream_passes_model_and_params(session, project):
    """调用 stream_collect 时 model / temperature / max_tokens / context 透传正确。"""
    svc, ai = _make_service(
        stream_collect_return={"content": _sample_bridge_json(1), "finish_reason": "stream_complete"}
    )

    await svc.plan_bridges(
        session,
        project_id="p-stream",
        model_name="claude-opus-4-7",
        bridge_count=1,
    )

    call_kwargs = ai.generate_text_stream_collect.await_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-7"
    assert call_kwargs["temperature"] == 0.6
    assert call_kwargs["max_tokens"] == 8000
    assert "BridgePlanning" in call_kwargs["context"]
    assert "claude-opus-4-7" in call_kwargs["context"]


@pytest.mark.asyncio
async def test_plan_bridges_stream_falls_back_to_default_model(session, project):
    """model_name=None 时应回退到 ai_service.default_model，并把它传给 stream_collect。"""
    svc, ai = _make_service(
        stream_collect_return={"content": _sample_bridge_json(1), "finish_reason": "stream_complete"}
    )

    await svc.plan_bridges(session, project_id="p-stream", model_name=None, bridge_count=1)

    call_kwargs = ai.generate_text_stream_collect.await_args.kwargs
    assert call_kwargs["model"] == "default-test-model"
    assert "default-test-model" in call_kwargs["context"]


@pytest.mark.asyncio
async def test_plan_bridges_stream_empty_array_raises(session, project):
    """流式返回空数组 → ValueError。"""
    svc, _ = _make_service(
        stream_collect_return={"content": "[]", "finish_reason": "stream_complete"}
    )

    with pytest.raises(ValueError, match="桥段列表为空"):
        await svc.plan_bridges(session, project_id="p-stream", bridge_count=1)


@pytest.mark.asyncio
async def test_plan_bridges_stream_non_array_raises(session, project):
    """流式返回 dict / 单对象 → safe_parse_json 配 expected_type='array' 兜底空 → ValueError。"""
    svc, _ = _make_service(
        stream_collect_return={"content": '{"not": "array"}', "finish_reason": "stream_complete"}
    )

    with pytest.raises(ValueError, match="桥段列表为空|格式错误"):
        await svc.plan_bridges(session, project_id="p-stream", bridge_count=1)


@pytest.mark.asyncio
async def test_plan_bridges_stream_propagates_underlying_exception(session, project):
    """流式底层持续 timeout / 网络错 → service 应原样抛出。"""
    import httpx

    svc, _ = _make_service(stream_collect_exc=httpx.ReadTimeout("network down"))

    with pytest.raises(httpx.ReadTimeout, match="network down"):
        await svc.plan_bridges(session, project_id="p-stream", bridge_count=1)


@pytest.mark.asyncio
async def test_plan_bridges_stream_skips_non_dict_items(session, project):
    """LLM 偶尔返 ['x', None, {...}, 123] 这种混合 → 应跳过非 dict 项，只入库合法对象。"""
    mixed = json.dumps(
        [
            "noise",
            None,
            {"bridge_number": 1, "title": "T1", "goal": "G1", "showoff_point": "S1"},
            42,
            {"bridge_number": 2, "title": "T2", "goal": "G2", "showoff_point": "S2"},
        ],
        ensure_ascii=False,
    )
    svc, _ = _make_service(
        stream_collect_return={"content": mixed, "finish_reason": "stream_complete"}
    )

    created = await svc.plan_bridges(session, project_id="p-stream", bridge_count=5)

    assert len(created) == 2
    assert [b.title for b in created] == ["T1", "T2"]
