"""V4.1 方案 C：build_plot_lines_with_beats slot builder 单元测试。

覆盖：
- 项目无 plot_lines → 返回空串
- 项目有 plot_line 但 timeline_data 为 None → 跳过该 line（空串）
- 单条主线 + 3 节点 + bridge_count=12 → 按 weight 分配 4 / 4 / 4 桥段
- 双线（主线 60% + 支线 40%）+ bridge_count=10 → 6/4 桥段，再按节点 weight 细分
- 节点权重非归一化（如 0.4 + 0.4 + 0.4 共 1.2）→ 应内部归一化避免越界
- 节点 weight 极小不舍五入（floor + 余数补足）→ 桥段总数严格 = line_quota
- ctx.extra["bridge_count"] 缺失 → 默认 25
- timeline_data JSON 损坏 → 跳过该 line
"""
from __future__ import annotations

import json
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db_base import Base
from app.models.plot_line import PlotLine
from app.models.project import Project
from app.services.reference_pack import AssemblyContext
from app.services.reference_pack.slot_builders import build_plot_lines_with_beats


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
    p = Project(id="p-builder", user_id="u1", title="测试书", status="planning")
    session.add(p)
    await session.commit()
    return p


def _ctx(bridge_count: int | None = None) -> AssemblyContext:
    extra: dict[str, Any] = {}
    if bridge_count is not None:
        extra["bridge_count"] = bridge_count
    return AssemblyContext(
        scene="bridge_planning",
        model_name="deepseek-v3",
        project_id="p-builder",
        extra=extra,
    )


async def _add_line(
    session: AsyncSession,
    *,
    title: str,
    beats: list[dict[str, Any]] | None,
    line_type: str = "main",
    estimated_chapters: int | None = 40,
    order_index: int = 0,
    timeline_data: str | None = None,
) -> PlotLine:
    if timeline_data is None and beats is not None:
        timeline_data = json.dumps({"beats": beats}, ensure_ascii=False)
    line = PlotLine(
        project_id="p-builder",
        title=title,
        line_type=line_type,
        estimated_chapters=estimated_chapters,
        order_index=order_index,
        timeline_data=timeline_data,
    )
    session.add(line)
    await session.commit()
    await session.refresh(line)
    return line


# ============================================================
# Tests
# ============================================================


@pytest.mark.asyncio
async def test_no_plot_lines_returns_empty(session, project):
    """项目无任何 plot_line → 返回空串。"""
    text = await build_plot_lines_with_beats(session, _ctx(25))
    assert text == ""


@pytest.mark.asyncio
async def test_plot_line_without_timeline_data_skipped(session, project):
    """plot_line 有但 timeline_data=None / beats=[] → 跳过该 line。"""
    await _add_line(session, title="L1", beats=None)  # 直接 timeline_data=None
    await _add_line(session, title="L2", beats=[])  # beats 空

    text = await build_plot_lines_with_beats(session, _ctx(10))
    assert text == ""


@pytest.mark.asyncio
async def test_single_main_line_three_beats_even_quota(session, project):
    """主线 1 条 3 节点 weight 1/3 每个，bridge_count=12 → 4/4/4 桥段。"""
    beats = [
        {"index": 1, "title": "起", "weight": 1 / 3, "description": "代入背景"},
        {"index": 2, "title": "承", "weight": 1 / 3, "description": "冲突升级"},
        {"index": 3, "title": "转", "weight": 1 / 3, "description": "高潮反转"},
    ]
    await _add_line(session, title="青云路", beats=beats, line_type="main", estimated_chapters=48)

    text = await build_plot_lines_with_beats(session, _ctx(12))

    # 含总桥段数
    assert "总桥段数：12" in text
    # 主线标题
    assert "主线：青云路" in text
    # 4 个桥段（每节点 4 = 12/3）
    assert "→ 4 个桥段" in text
    # 三个节点都列出
    assert "[节点 1]" in text
    assert "[节点 2]" in text
    assert "[节点 3]" in text


@pytest.mark.asyncio
async def test_two_lines_quota_split_by_estimated_chapters(session, project):
    """主线 60 章 + 支线 40 章，bridge_count=10 → 主线 6 桥段 + 支线 4 桥段。"""
    main_beats = [
        {"index": 1, "title": "M1", "weight": 0.5},
        {"index": 2, "title": "M2", "weight": 0.5},
    ]
    sub_beats = [
        {"index": 1, "title": "S1", "weight": 1.0},
    ]
    await _add_line(
        session, title="主线", beats=main_beats, line_type="main", estimated_chapters=60, order_index=0
    )
    await _add_line(
        session, title="支线", beats=sub_beats, line_type="sub", estimated_chapters=40, order_index=1
    )

    text = await build_plot_lines_with_beats(session, _ctx(10))

    # 主线 6 桥段（60/100*10）→ 两节点各 3 桥段
    assert "主线：主线" in text
    assert "支线：支线" in text
    # 主线两节点都应分到桥段
    main_section_start = text.index("主线：主线")
    sub_section_start = text.index("支线：支线")
    main_section = text[main_section_start:sub_section_start]
    sub_section = text[sub_section_start:]
    # 主线总桥段 = 6
    main_quota_total = sum(int(line.split("→")[-1].strip().split(" ")[0])
                            for line in main_section.split("\n")
                            if "个桥段" in line and "[节点" in line)
    assert main_quota_total == 6
    # 支线唯一节点 = 4
    sub_quota_total = sum(int(line.split("→")[-1].strip().split(" ")[0])
                           for line in sub_section.split("\n")
                           if "个桥段" in line and "[节点" in line)
    assert sub_quota_total == 4


@pytest.mark.asyncio
async def test_quota_floor_and_remainder_strictly_sums_to_line_quota(session, project):
    """节点权重不能整除时（如 3 节点 + 10 桥段 → 3.33/节点），
    floor + 余数补足应使桥段总数严格 = line 配额。"""
    beats = [
        {"index": 1, "title": "A", "weight": 0.333},
        {"index": 2, "title": "B", "weight": 0.333},
        {"index": 3, "title": "C", "weight": 0.334},
    ]
    await _add_line(session, title="L", beats=beats, line_type="main", estimated_chapters=40)

    text = await build_plot_lines_with_beats(session, _ctx(10))

    total = sum(
        int(line.split("→")[-1].strip().split(" ")[0])
        for line in text.split("\n")
        if "个桥段" in line and "[节点" in line
    )
    assert total == 10  # 严格等于 bridge_count


@pytest.mark.asyncio
async def test_non_normalized_beat_weights_are_internally_normalized(session, project):
    """节点 weight 总和不为 1（如 0.4+0.4+0.4=1.2）→ builder 应内部按总和归一化，
    不至于导致 quota 超出 line 配额。"""
    beats = [
        {"index": 1, "title": "A", "weight": 0.4},
        {"index": 2, "title": "B", "weight": 0.4},
        {"index": 3, "title": "C", "weight": 0.4},  # 合 1.2
    ]
    await _add_line(session, title="L", beats=beats, line_type="main", estimated_chapters=40)

    text = await build_plot_lines_with_beats(session, _ctx(9))

    total = sum(
        int(line.split("→")[-1].strip().split(" ")[0])
        for line in text.split("\n")
        if "个桥段" in line and "[节点" in line
    )
    # 单 line 配额 = 9（全 estimated），归一化后每节点 1/3 → 3/3/3
    assert total == 9


@pytest.mark.asyncio
async def test_default_bridge_count_when_extra_missing(session, project):
    """ctx.extra 不含 bridge_count → 默认 25。"""
    beats = [{"index": 1, "title": "A", "weight": 1.0}]
    await _add_line(session, title="L", beats=beats, line_type="main", estimated_chapters=40)

    text = await build_plot_lines_with_beats(session, _ctx(None))

    assert "总桥段数：25" in text


@pytest.mark.asyncio
async def test_corrupt_timeline_data_skipped(session, project):
    """timeline_data 是损坏 JSON → 该 line 跳过，不抛异常。"""
    # 损坏 JSON
    await _add_line(
        session, title="坏 line", beats=None, timeline_data="not json {"
    )
    # 正常 line
    beats = [{"index": 1, "title": "A", "weight": 1.0}]
    await _add_line(session, title="好 line", beats=beats, line_type="main", estimated_chapters=20)

    text = await build_plot_lines_with_beats(session, _ctx(5))
    # 损坏的应被跳过；正常的应出现
    assert "坏 line" not in text
    assert "好 line" in text
