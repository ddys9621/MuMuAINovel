"""V4.1 方案 C：BridgePlanningService.plan_bridges 在 by_plot_line 模式下的行为。

覆盖：
- mode='by_plot_line' 时 ctx.extra 透传 bridge_count + plan_mode
- mode='by_plot_line' 时若 plot_lines_with_beats slot filled → 用 BY_PLOT_LINE prompt
- mode='by_plot_line' 时若 plot_lines_with_beats slot 缺失 → 回退 FREE prompt
- mode='free' → 始终用 FREE prompt
- 入库时 plot_line_id / beat_index / coverage_start / coverage_end 持久化
- coverage 越界 / 类型错误 → 调用 _clamp01 钳制
- 非法 mode 抛 ValueError
- expand_bridge_to_chapters 在桥段绑节点时调 _load_beat_context_for_bridge 注入 prompt
- expand 在桥段未绑节点时不注入 beat 块（向后兼容 free / 老数据）
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
from app.models.plot_line import PlotLine
from app.models.project import Project
from app.services.bridge_planning_service import (
    BRIDGE_PLANNING_TASK_PROMPT_BY_PLOT_LINE,
    BRIDGE_PLANNING_TASK_PROMPT_FREE,
    BridgePlanningService,
    _clamp01,
    _load_beat_context_for_bridge,
)
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
    p = Project(id="p-mode", user_id="u1", title="测试", status="planning")
    session.add(p)
    await session.commit()
    return p


def _make_assembled(slots_filled: list[str] | None = None) -> AssembledPrompt:
    return AssembledPrompt(
        system_prompt="sys",
        user_prompt="user",
        user_blocks=[],
        slots_filled=slots_filled or ["project_skeleton"],
        slots_truncated=[],
        slots_skipped=[],
        actual_tokens_estimate=1000,
    )


def _make_service(assembled: AssembledPrompt, content: str):
    ai = MagicMock()
    ai.default_model = "default-model"
    ai.generate_text_stream_collect = AsyncMock(
        return_value={"content": content, "finish_reason": "stream_complete"}
    )
    svc = BridgePlanningService(ai_service=ai)
    svc.assembler = MagicMock()
    svc.assembler.assemble = AsyncMock(return_value=assembled)
    return svc, ai


def _by_plot_line_bridges_json(n: int = 2, line_id: str = "line-1") -> str:
    arr = []
    for i in range(n):
        arr.append({
            "bridge_number": i + 1,
            "plot_line_id": line_id,
            "beat_index": 1,
            "beat_coverage_start": i / n,
            "beat_coverage_end": (i + 1) / n,
            "title": f"桥段 {i + 1}",
            "goal": f"目标 {i + 1}",
            "showoff_point": f"爽点 {i + 1}",
        })
    return json.dumps(arr, ensure_ascii=False)


# ============================================================
# _clamp01 unit tests
# ============================================================


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0.5, 0.5),
        (0, 0.0),
        (1, 1.0),
        (1.5, 1.0),  # 越界 → 钳制
        (-0.5, 0.0),
        ("0.3", 0.3),  # 字符串 → 转 float
        ("abc", None),
        (None, None),
        ({}, None),
    ],
)
def test_clamp01_handles_various_inputs(raw, expected):
    assert _clamp01(raw) == expected


# ============================================================
# plan_bridges mode 行为
# ============================================================


@pytest.mark.asyncio
async def test_plan_invalid_mode_raises(session, project):
    """非法 mode → ValueError。"""
    svc, _ = _make_service(_make_assembled(), "[]")
    with pytest.raises(ValueError, match="unknown mode"):
        await svc.plan_bridges(session, project_id="p-mode", mode="invalid")


@pytest.mark.asyncio
async def test_plan_by_plot_line_passes_extra_bridge_count(session, project):
    """ctx.extra['bridge_count'] 和 plan_mode 应正确透传给 assembler。"""
    svc, _ = _make_service(
        _make_assembled(["project_skeleton", "plot_lines_with_beats"]),
        _by_plot_line_bridges_json(2),
    )

    await svc.plan_bridges(
        session, project_id="p-mode", bridge_count=15, mode="by_plot_line"
    )

    call = svc.assembler.assemble.await_args
    ctx = call.args[1]
    assert ctx.scene == "bridge_planning"
    assert ctx.extra == {"bridge_count": 15, "plan_mode": "by_plot_line"}


@pytest.mark.asyncio
async def test_plan_by_plot_line_uses_by_plot_line_prompt_when_slot_filled(session, project):
    """slots_filled 含 plot_lines_with_beats → 使用 BY_PLOT_LINE 模板。"""
    svc, ai = _make_service(
        _make_assembled(["project_skeleton", "plot_lines_with_beats"]),
        _by_plot_line_bridges_json(2),
    )

    await svc.plan_bridges(session, project_id="p-mode", mode="by_plot_line")

    sent_prompt = ai.generate_text_stream_collect.await_args.kwargs["prompt"]
    # BY_PLOT_LINE 模板独有特征
    assert "V4.1 方案 C：分层契合规则" in sent_prompt
    assert "plot_line_id" in sent_prompt


@pytest.mark.asyncio
async def test_plan_by_plot_line_falls_back_to_free_when_slot_missing(session, project):
    """slots_filled 不含 plot_lines_with_beats（项目无 plot_lines）→ 退化为 FREE 模板。"""
    svc, ai = _make_service(
        _make_assembled(["project_skeleton"]),  # 缺 plot_lines_with_beats
        _by_plot_line_bridges_json(1),  # 即便 LLM 仍按 by_plot_line 返，也只是多余字段，能被忽略
    )

    await svc.plan_bridges(session, project_id="p-mode", mode="by_plot_line")

    sent_prompt = ai.generate_text_stream_collect.await_args.kwargs["prompt"]
    # FREE 模板没有这两个特征
    assert "V4.1 方案 C：分层契合规则" not in sent_prompt


@pytest.mark.asyncio
async def test_plan_free_mode_always_uses_free_prompt(session, project):
    """mode='free' → 不管 slot 状态，都用 FREE 模板。"""
    svc, ai = _make_service(
        _make_assembled(["project_skeleton", "plot_lines_with_beats"]),
        json.dumps([{"bridge_number": 1, "title": "T", "goal": "G", "showoff_point": "S"}]),
    )

    await svc.plan_bridges(session, project_id="p-mode", mode="free")

    sent_prompt = ai.generate_text_stream_collect.await_args.kwargs["prompt"]
    assert "V4.1 方案 C：分层契合规则" not in sent_prompt


@pytest.mark.asyncio
async def test_plan_by_plot_line_persists_beat_binding_fields(session, project):
    """by_plot_line 模式入库时 plot_line_id / beat_index / coverage 应被持久化。"""
    svc, _ = _make_service(
        _make_assembled(["project_skeleton", "plot_lines_with_beats"]),
        _by_plot_line_bridges_json(2, line_id="line-A"),
    )

    created = await svc.plan_bridges(session, project_id="p-mode", mode="by_plot_line")

    assert len(created) == 2
    assert all(b.plot_line_id == "line-A" for b in created)
    assert all(b.beat_index == 1 for b in created)
    assert created[0].beat_coverage_start == 0.0
    assert created[0].beat_coverage_end == 0.5
    assert created[1].beat_coverage_start == 0.5
    assert created[1].beat_coverage_end == 1.0

    # DB 校验
    rows = (await session.execute(select(PlotBridge))).scalars().all()
    assert {r.plot_line_id for r in rows} == {"line-A"}


@pytest.mark.asyncio
async def test_plan_clamps_out_of_range_coverage(session, project):
    """LLM 偶尔输出 coverage_start=-0.1 / coverage_end=1.5 → 应被 _clamp01 钳制。"""
    bad = json.dumps([
        {
            "bridge_number": 1,
            "plot_line_id": "line-X",
            "beat_index": 1,
            "beat_coverage_start": -0.1,
            "beat_coverage_end": 1.5,
            "title": "T",
            "goal": "G",
            "showoff_point": "S",
        }
    ])
    svc, _ = _make_service(_make_assembled(["plot_lines_with_beats"]), bad)

    created = await svc.plan_bridges(session, project_id="p-mode", mode="by_plot_line")

    assert created[0].beat_coverage_start == 0.0
    assert created[0].beat_coverage_end == 1.0


@pytest.mark.asyncio
async def test_plan_ignores_invalid_beat_fields(session, project):
    """LLM 输出 plot_line_id 是 int / beat_index 是字符串 → 应被忽略保持 None。"""
    bad = json.dumps([
        {
            "bridge_number": 1,
            "plot_line_id": 12345,  # 应为 str
            "beat_index": "not int",
            "beat_coverage_start": None,
            "beat_coverage_end": None,
            "title": "T",
            "goal": "G",
            "showoff_point": "S",
        }
    ])
    svc, _ = _make_service(_make_assembled(), bad)

    created = await svc.plan_bridges(session, project_id="p-mode", mode="free")

    assert created[0].plot_line_id is None
    assert created[0].beat_index is None
    assert created[0].beat_coverage_start is None
    assert created[0].beat_coverage_end is None


# ============================================================
# _load_beat_context_for_bridge unit tests
# ============================================================


def _build_line_with_beats(line_id: str, beats: list[dict]) -> PlotLine:
    return PlotLine(
        id=line_id,
        project_id="p-mode",
        title="主线《青云路》",
        line_type="main",
        estimated_chapters=40,
        timeline_data=json.dumps({"beats": beats}, ensure_ascii=False),
    )


@pytest.mark.asyncio
async def test_load_beat_context_returns_empty_when_bridge_unbound(session):
    """桥段没绑节点 → 返回空串。"""
    b = PlotBridge(
        project_id="p-mode", bridge_number=1, title="T",
        goal="G", showoff_point="S", plot_line_id=None, beat_index=None,
    )
    text = await _load_beat_context_for_bridge(session, b)
    assert text == ""


@pytest.mark.asyncio
async def test_load_beat_context_returns_empty_when_line_missing(session):
    """桥段绑了 plot_line_id 但 plot_line 不存在 → 返回空串（不抛错）。"""
    b = PlotBridge(
        project_id="p-mode", bridge_number=1, title="T",
        goal="G", showoff_point="S", plot_line_id="ghost", beat_index=1,
    )
    text = await _load_beat_context_for_bridge(session, b)
    assert text == ""


@pytest.mark.asyncio
async def test_load_beat_context_full_structure(session, project):
    """完整路径：返回含剧情线 / 节点 / 进度 / 上下节点的文本块。"""
    beats = [
        {"index": 1, "title": "起", "weight": 0.3, "description": "代入背景"},
        {"index": 2, "title": "承", "weight": 0.4, "description": "冲突升级"},
        {"index": 3, "title": "转", "weight": 0.3, "description": "高潮反转"},
    ]
    session.add(_build_line_with_beats("line-X", beats))
    await session.commit()

    b = PlotBridge(
        project_id="p-mode", bridge_number=5, title="T",
        goal="G", showoff_point="S",
        plot_line_id="line-X", beat_index=2,
        beat_coverage_start=0.25, beat_coverage_end=0.5,
    )

    text = await _load_beat_context_for_bridge(session, b)
    assert "剧情线：主线《主线《青云路》》" in text or "主线《青云路》" in text  # title 已含书名号
    assert "[节点 2]" in text
    assert "承" in text
    assert "25%" in text and "50%" in text
    # 上下节点
    assert "上一节点：[节点 1] 起" in text
    assert "下一节点：[节点 3] 转" in text


@pytest.mark.asyncio
async def test_load_beat_context_first_beat_no_prev(session, project):
    """beat_index=1 → 没有上一节点。"""
    beats = [
        {"index": 1, "title": "起", "weight": 0.5},
        {"index": 2, "title": "承", "weight": 0.5},
    ]
    session.add(_build_line_with_beats("line-Y", beats))
    await session.commit()

    b = PlotBridge(
        project_id="p-mode", bridge_number=1, title="T",
        goal="G", showoff_point="S",
        plot_line_id="line-Y", beat_index=1,
        beat_coverage_start=0.0, beat_coverage_end=0.5,
    )
    text = await _load_beat_context_for_bridge(session, b)
    assert "上一节点" not in text
    assert "下一节点：[节点 2] 承" in text


@pytest.mark.asyncio
async def test_load_beat_context_last_beat_no_next(session, project):
    """beat_index 是最后一个 → 没有下一节点。"""
    beats = [
        {"index": 1, "title": "起", "weight": 0.5},
        {"index": 2, "title": "终", "weight": 0.5},
    ]
    session.add(_build_line_with_beats("line-Z", beats))
    await session.commit()

    b = PlotBridge(
        project_id="p-mode", bridge_number=1, title="T",
        goal="G", showoff_point="S",
        plot_line_id="line-Z", beat_index=2,
        beat_coverage_start=0.5, beat_coverage_end=1.0,
    )
    text = await _load_beat_context_for_bridge(session, b)
    assert "上一节点：[节点 1]" in text
    assert "下一节点" not in text
