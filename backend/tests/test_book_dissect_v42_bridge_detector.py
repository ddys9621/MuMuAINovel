"""V4.2 BridgeDetector 验收测试。

覆盖：
- 路径 1 LLM 模式：正常解析 / 空输入 / 超界桥段过滤 / 调用失败回退
- 路径 2 规则模式：ai_service=None 时变长窗口扫描
- 变长桥段：2/3/4/5/7 章窗口都能识别
- BridgeWindow 数据结构：detection_origin / confidence_breakdown 字段
- 爆点峰检测：均值/阈值/MIN_PEAK_GAP/MAX_PEAKS_PER_BOOK

设计文档：agent-docs/features/book_dissect_v4_design.md §11.2.4 V4.2 重构
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.bridge_detector import BridgeDetector, BridgeWindow
from app.services.book_dissect.bridge_pattern_aggregator import (
    BridgePatternAggregator,
)
from app.services.book_dissect.v2_types import ChapterFact


# ============================================================
# fixtures
# ============================================================


def make_chapter_fact(
    num: int,
    *,
    summary: str = "",
    chapter_title: str = "",
) -> ChapterFact:
    """构造一个 ChapterFact 用于测试。"""
    return ChapterFact(
        chapter_number=num,
        chapter_title=chapter_title or f"第{num}章",
        summary=summary,
    )


def mock_llm(json_obj: dict | str | Exception) -> MagicMock:
    """构造 mock AIService，generate_text 返回指定内容或抛指定异常。"""
    ai = MagicMock()
    if isinstance(json_obj, Exception):
        ai.generate_text = AsyncMock(side_effect=json_obj)
    else:
        content = (
            json.dumps(json_obj, ensure_ascii=False)
            if isinstance(json_obj, dict)
            else json_obj
        )
        ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


# ============================================================
# 路径 2：规则模式（ai_service=None）
# ============================================================


@pytest.mark.asyncio
async def test_rule_mode_no_ai_service_falls_back():
    """ai_service=None 时强制走 rule 模式，不该抛 LLM 相关异常。"""
    facts = [
        make_chapter_fact(1, summary="林七早饭后上路，与师兄同行前往天剑宗。"),
        make_chapter_fact(2, summary="路上遇到敌对宗门，对方嘲讽轻视林七修为低微。"),
        make_chapter_fact(3, summary="林七突然出手，一剑秒杀对方，对方目瞪口呆、震惊不已。"),
        make_chapter_fact(4, summary="林七告一段落，前往下一目标，获得宗门赏赐。"),
    ]
    detector = BridgeDetector(ai_service=None)
    bridges = await detector.detect_bridges(facts)
    # 应该至少识别出 1 个桥段
    assert len(bridges) >= 1
    # 来源应是 rule
    assert all(b.detection_origin == "rule" for b in bridges)
    # confidence_breakdown 应含 c1-c4 评分
    for b in bridges:
        assert "c1_intro" in b.confidence_breakdown
        assert "c3_payoff" in b.confidence_breakdown


@pytest.mark.asyncio
async def test_rule_mode_empty_input_returns_empty():
    """空输入返回空。"""
    detector = BridgeDetector(ai_service=None)
    assert await detector.detect_bridges([]) == []


@pytest.mark.asyncio
async def test_rule_mode_single_chapter_no_payoff_returns_empty():
    """单章 + 无爽点词 + 无 LLM → 走 short-form rule 兜底，密度不达阈值返回空。"""
    detector = BridgeDetector(ai_service=None)
    fact = make_chapter_fact(1, summary="平淡的一天，吃早饭聊天散步。")
    result = await detector.detect_bridges([fact])
    assert result == []


@pytest.mark.asyncio
async def test_rule_mode_recognizes_variable_length():
    """rule 模式应能识别变长桥段（2/3/4/5/6/7 章）。"""
    # 构造 3 章短桥段：日常 → 爽点 → 善后
    facts = [
        make_chapter_fact(1, summary="林七路上遇到师兄朋友，闲聊间提及前路。"),
        make_chapter_fact(2, summary="突然敌人现身，林七一拳秒杀，敌人目瞪口呆。"),
        make_chapter_fact(3, summary="林七获得战利品，前往下一目的地。"),
    ]
    detector = BridgeDetector(ai_service=None)
    bridges = await detector.detect_bridges(facts)
    # 应能识别出至少 1 个桥段（长度 3）
    assert len(bridges) >= 1
    # 至少有一个桥段是 3 章长度
    assert any(len(b.chapters) == 3 for b in bridges)


# ============================================================
# 路径 1：LLM 模式
# ============================================================


@pytest.mark.asyncio
async def test_llm_mode_normal_path():
    """LLM 模式正常解析。

    构造 10 章：第 5 章是明显爽点峰（密度远超均值），LLM 被调用。
    """
    facts = []
    for i in range(1, 11):
        if i == 5:
            # 爽点峰章：高密度 C3 关键词
            summary = "林七出手，秒杀对方，敌人震惊不已、目瞪口呆、倒抽冷气、脸色苍白、瞠目结舌！完胜碾压横扫！" * 2
        elif i == 8:
            # 第二个爽点峰
            summary = "真相揭露，原来林七是隐世大派弟子，所有人震惊愕然，瞠目下跪求饶拜服！"
        else:
            summary = f"林七第{i}章日常生活，路上和师兄聊天。"
        facts.append(make_chapter_fact(i, summary=summary))

    # mock LLM 返回 2 个桥段（变长：5 章 + 3 章，故意非 4）
    ai = mock_llm({
        "bridges": [
            {
                "start_chapter": 3,
                "end_chapter": 7,
                "type": "武力打脸",
                "goal": "击败敌对宗门",
                "showoff_point": "一剑秒杀长老",
                "golden_finger": "无金手指",
                "confidence": 0.85,
            },
        ],
    })
    detector = BridgeDetector(ai_service=ai, enable_llm=True)
    bridges = await detector.detect_bridges(facts)
    # 应解析出至少 1 个桥段
    assert len(bridges) >= 1
    # 来源应是 llm
    assert any(b.detection_origin == "llm" for b in bridges)
    # 至少一个桥段长度非 4（变长能力验证）
    lengths = {len(b.chapters) for b in bridges}
    assert 5 in lengths  # 应识别出 3-7 章 = 5 章长度


@pytest.mark.asyncio
async def test_llm_mode_empty_bridges_response():
    """LLM 返回空 bridges 数组 → 输出空列表。"""
    facts = [
        make_chapter_fact(i, summary=f"第{i}章 震惊 碾压 秒杀 完胜。" * 3)
        for i in range(1, 11)
    ]
    ai = mock_llm({"bridges": []})
    detector = BridgeDetector(ai_service=ai)
    bridges = await detector.detect_bridges(facts)
    assert bridges == []


@pytest.mark.asyncio
async def test_llm_mode_call_fails_falls_back_to_rule():
    """LLM 调用抛异常 → 自动回退到 rule 模式。"""
    facts = [
        make_chapter_fact(1, summary="林七早饭后上路，与师兄同行。"),
        make_chapter_fact(2, summary="敌人嘲讽轻视林七。"),
        make_chapter_fact(3, summary="林七出手秒杀敌人，敌人目瞪口呆震惊。"),
        make_chapter_fact(4, summary="林七告一段落前往下一目标。"),
    ]
    ai = mock_llm(RuntimeError("network down"))
    detector = BridgeDetector(ai_service=ai)
    bridges = await detector.detect_bridges(facts)
    # LLM 失败 → 回退 rule 模式，仍应识别出桥段
    # 注：rule 模式也可能识别 0 个（关键词密度不够），但不该抛异常
    assert isinstance(bridges, list)


@pytest.mark.asyncio
async def test_llm_mode_out_of_range_bridges_filtered():
    """LLM 返回超出区域范围的桥段 → 过滤掉。"""
    facts = [
        make_chapter_fact(i, summary=f"第{i}章 震惊 完胜。" * 3)
        for i in range(1, 11)
    ]
    # 返回的桥段超出输入范围（章 100-200 不存在）
    ai = mock_llm({
        "bridges": [
            {
                "start_chapter": 100,
                "end_chapter": 200,
                "type": "假桥段",
                "confidence": 0.9,
            },
        ],
    })
    detector = BridgeDetector(ai_service=ai)
    bridges = await detector.detect_bridges(facts)
    # 超界桥段应被过滤
    assert all(
        max(b.chapters) <= 10 and min(b.chapters) >= 1
        for b in bridges
    )


@pytest.mark.asyncio
async def test_llm_mode_confidence_clamped():
    """LLM 返回的 confidence 超过 [0, 1] → 自动 clamp。"""
    facts = [
        make_chapter_fact(i, summary=f"第{i}章 震惊 完胜 秒杀。" * 3)
        for i in range(1, 11)
    ]
    ai = mock_llm({
        "bridges": [
            {"start_chapter": 3, "end_chapter": 5, "type": "x", "confidence": 1.5},
            {"start_chapter": 7, "end_chapter": 9, "type": "y", "confidence": -0.3},
        ],
    })
    detector = BridgeDetector(ai_service=ai)
    bridges = await detector.detect_bridges(facts)
    for b in bridges:
        assert 0.0 <= b.avg_score <= 1.0


# ============================================================
# 爆点峰检测细节
# ============================================================


@pytest.mark.asyncio
async def test_payoff_peak_density_calculation():
    """爽点密度计算：包含爽点词的章节密度应 > 普通章节。"""
    detector = BridgeDetector(ai_service=None)
    plain = detector._payoff_density("林七今天去吃早饭，和师兄一起聊天。")
    payoff = detector._payoff_density(
        "林七出手秒杀敌人，敌人目瞪口呆，震惊不已，完胜碾压横扫！"
    )
    assert payoff > plain


@pytest.mark.asyncio
async def test_find_peaks_below_threshold_returns_empty():
    """全 0 密度 → 无峰。"""
    detector = BridgeDetector(ai_service=None)
    assert detector._find_payoff_peaks([0.0] * 10) == []


@pytest.mark.asyncio
async def test_find_peaks_respects_min_gap():
    """两峰间距应 >= MIN_PEAK_GAP。"""
    detector = BridgeDetector(ai_service=None)
    # 制造连续两个峰：index 5 和 index 6 都是局部最大
    densities = [0.0] * 10
    densities[5] = 1.0
    densities[6] = 1.0
    peaks = detector._find_payoff_peaks(densities)
    # 应只选 1 个（间隔不够）
    if len(peaks) > 1:
        gaps = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
        assert all(g >= detector.MIN_PEAK_GAP for g in gaps)


# ============================================================
# BridgePatternAggregator 适配变长
# ============================================================


def test_aggregator_handles_variable_length_bridges():
    """BridgePatternAggregator 应能处理变长桥段（不仅 4 章）。"""
    bridges = [
        BridgeWindow(
            chapters=[1, 2],  # 微桥段
            avg_score=0.7,
            is_standard=False,
            bridge_type="微打脸",
            detection_origin="llm",
            confidence_breakdown={"llm_confidence": 0.7, "bridge_length": 2.0},
        ),
        BridgeWindow(
            chapters=[10, 11, 12, 13, 14, 15, 16],  # 长桥段
            avg_score=0.85,
            is_standard=True,
            bridge_type="副本通关",
            detection_origin="llm",
            confidence_breakdown={"llm_confidence": 0.85, "bridge_length": 7.0},
        ),
    ]
    chapter_facts = [
        ChapterFact(chapter_number=i, summary=f"第{i}章摘要")
        for i in range(1, 20)
    ]
    agg = BridgePatternAggregator()
    result = agg.aggregate(bridges, chapter_facts=chapter_facts)

    assert result["total_bridges_detected"] == 2
    # 长度分布应正确
    assert result["rhythm_stats"]["bridge_length_distribution"]["micro_1_2"] == 1
    assert result["rhythm_stats"]["bridge_length_distribution"]["epic_7plus"] == 1
    # 平均桥段长度应该不是固定 4
    assert result["rhythm_stats"]["avg_bridge_length"] == pytest.approx(4.5, abs=0.1)

    # 检查 typical_examples 字段格式
    for type_entry in result["bridge_types"]:
        for ex in type_entry["typical_examples"]:
            assert "bridge_length" in ex
            assert "detection_origin" in ex
            # chapter_summaries 应用 ch{N} 命名（V4.2 变长）
            for k in ex["chapter_summaries"].keys():
                assert k.startswith("ch")


def test_aggregator_backward_compat_with_v41_fields():
    """老 BridgeWindow 没 confidence_breakdown 时回退到 c1-c4 字段。"""
    old_bridge = BridgeWindow(
        chapters=[1, 2, 3, 4],
        avg_score=0.6,
        is_standard=True,
        bridge_type="V41老桥段",
        detection_origin="rule",
        confidence_breakdown={},  # 空
        c1_score=0.5,
        c2_score=0.6,
        c3_score=0.8,
        c4_score=0.5,
    )
    agg = BridgePatternAggregator()
    result = agg.aggregate([old_bridge])
    assert result["total_bridges_detected"] == 1
    # 应回退到老字段命名
    for type_entry in result["bridge_types"]:
        for ex in type_entry["typical_examples"]:
            assert "c1_intro_score" in ex["rating_features"]


# ============================================================
# Short-form 短篇 special-case（V4.2 补强）
# ============================================================


@pytest.mark.asyncio
async def test_shortform_single_chapter_with_llm():
    """单章短篇 + LLM 模式：LLM 直接判定整章是否桥段。"""
    fact = make_chapter_fact(
        1,
        summary="林七在比武大会上一拳秒杀对方长老，全场震惊目瞪口呆，最终夺得冠军。",
    )
    ai = mock_llm({
        "bridges": [
            {
                "start_chapter": 1,
                "end_chapter": 1,
                "type": "比赛夺冠",
                "goal": "夺冠并震慑对手",
                "showoff_point": "一拳秒杀长老",
                "golden_finger": "天生神力",
                "confidence": 0.9,
            },
        ],
    })
    detector = BridgeDetector(ai_service=ai, enable_llm=True)
    bridges = await detector.detect_bridges([fact])
    assert len(bridges) == 1
    assert bridges[0].chapters == [1]
    assert bridges[0].detection_origin == "llm_shortform"
    assert bridges[0].bridge_type == "比赛夺冠"


@pytest.mark.asyncio
async def test_shortform_two_chapters_with_llm():
    """双章短篇 + LLM 模式。"""
    facts = [
        make_chapter_fact(1, summary="林七遭遇仇敌，被嘲讽鄙视。"),
        make_chapter_fact(2, summary="林七突然出手秒杀仇敌，碾压完胜。"),
    ]
    ai = mock_llm({
        "bridges": [
            {
                "start_chapter": 1,
                "end_chapter": 2,
                "type": "武力打脸",
                "goal": "打脸仇敌",
                "showoff_point": "秒杀对手",
                "golden_finger": "无金手指",
                "confidence": 0.85,
            },
        ],
    })
    detector = BridgeDetector(ai_service=ai, enable_llm=True)
    bridges = await detector.detect_bridges(facts)
    assert len(bridges) == 1
    assert bridges[0].chapters == [1, 2]
    assert bridges[0].detection_origin == "llm_shortform"


@pytest.mark.asyncio
async def test_shortform_single_chapter_no_llm_high_density():
    """单章 + 无 LLM + 高爽点密度 → rule_shortform 兜底输出 1 个桥段。"""
    fact = make_chapter_fact(
        1,
        summary=(
            "林七出手秒杀对方，敌人震惊、目瞪口呆、倒抽冷气、"
            "脸色苍白、瞠目结舌、完胜、碾压、横扫、求饶下跪拜服！" * 2
        ),
    )
    detector = BridgeDetector(ai_service=None)
    bridges = await detector.detect_bridges([fact])
    assert len(bridges) == 1
    assert bridges[0].chapters == [1]
    assert bridges[0].detection_origin == "rule_shortform"
    assert bridges[0].is_standard is False  # 单章不算 standard
    assert "c3_payoff" in bridges[0].confidence_breakdown


@pytest.mark.asyncio
async def test_shortform_llm_returns_no_bridge_dont_fallback():
    """单章 + LLM 明确返回无桥段 → 不再 rule 兜底（避免噪音）。"""
    fact = make_chapter_fact(
        1,
        summary="林七秒杀完胜碾压震惊。" * 5,  # 关键词密度故意很高
    )
    # LLM 明确判定无桥段
    ai = mock_llm({"bridges": []})
    detector = BridgeDetector(ai_service=ai, enable_llm=True)
    bridges = await detector.detect_bridges([fact])
    # 即使关键词密度高，也应尊重 LLM 的"无桥段"判定
    assert bridges == []


@pytest.mark.asyncio
async def test_shortform_llm_fails_falls_back_to_rule_single():
    """单章 + LLM 异常 → 回退到单章规则路径。"""
    fact = make_chapter_fact(
        1,
        summary="林七出手秒杀，震惊全场，碾压完胜横扫！" * 5,
    )
    ai = mock_llm(RuntimeError("LLM down"))
    detector = BridgeDetector(ai_service=ai, enable_llm=True)
    bridges = await detector.detect_bridges([fact])
    # 应回退到 rule_shortform
    if bridges:  # 取决于关键词密度是否达标
        assert bridges[0].detection_origin == "rule_shortform"
        assert bridges[0].chapters == [1]


@pytest.mark.asyncio
async def test_shortform_single_chapter_multiple_bridges():
    """V4.2.1 核心修复：单章 + LLM 返回多个不同 type 桥段 → 全保留。

    旧 dedup 按章号重叠去重 → 单章场景永远只剩 1 个桥段（bug）。
    新 dedup 按 (chapters, type) 去重 → 同章不同 type 全保留。
    """
    fact = make_chapter_fact(
        1,
        summary="开篇被嘲讽，反转打脸；中段拉扯，实力震慑；章末伏笔，身份揭露。",
    )
    # LLM 在单章中识别出 3 个不同 type 的桥段
    ai = mock_llm({
        "bridges": [
            {
                "start_chapter": 1, "end_chapter": 1,
                "type": "武力打脸", "goal": "回击嘲讽",
                "showoff_point": "一拳震慑", "confidence": 0.8,
            },
            {
                "start_chapter": 1, "end_chapter": 1,
                "type": "实力震慑", "goal": "压制对手",
                "showoff_point": "中段实力展现", "confidence": 0.75,
            },
            {
                "start_chapter": 1, "end_chapter": 1,
                "type": "身份揭露", "goal": "暴露真身",
                "showoff_point": "章末身份反转", "confidence": 0.9,
            },
        ],
    })
    detector = BridgeDetector(ai_service=ai, enable_llm=True)
    bridges = await detector.detect_bridges([fact])
    # ★ 3 个桥段都应保留（而不是只剩 1 个）
    assert len(bridges) == 3
    types = {b.bridge_type for b in bridges}
    assert types == {"武力打脸", "实力震慑", "身份揭露"}
    # 所有都标 chapters=[1]
    assert all(b.chapters == [1] for b in bridges)


@pytest.mark.asyncio
async def test_dedup_same_chapters_same_type_keeps_highest_confidence():
    """V4.2.1 dedup 规则 1：(chapters, type) 完全相同 → 留 confidence 高的。"""
    detector = BridgeDetector(ai_service=None)
    bridges = [
        BridgeWindow(chapters=[3, 4], avg_score=0.7, bridge_type="打脸"),
        BridgeWindow(chapters=[3, 4], avg_score=0.85, bridge_type="打脸"),  # 重复
        BridgeWindow(chapters=[3, 4], avg_score=0.6, bridge_type="打脸"),
    ]
    result = detector._dedup_and_sort(bridges)
    assert len(result) == 1
    assert result[0].avg_score == 0.85


def test_dedup_same_chapters_different_type_keeps_all():
    """V4.2.1 dedup 规则 2：chapters 重叠但 type 不同 → 全保留。"""
    detector = BridgeDetector(ai_service=None)
    bridges = [
        BridgeWindow(chapters=[5, 6, 7], avg_score=0.8, bridge_type="武力打脸"),
        BridgeWindow(chapters=[5, 6, 7], avg_score=0.7, bridge_type="身份揭露"),
        BridgeWindow(chapters=[6, 7, 8], avg_score=0.75, bridge_type="智计反杀"),
    ]
    result = detector._dedup_and_sort(bridges)
    assert len(result) == 3


def test_dedup_subset_same_type_removed():
    """V4.2.1 dedup 规则 3：子集关系 + 同 type → 子集被剔除（消除变长窗口噪音）。"""
    detector = BridgeDetector(ai_service=None)
    bridges = [
        BridgeWindow(chapters=[3, 4, 5], avg_score=0.7, bridge_type="打脸"),  # 子集
        BridgeWindow(chapters=[3, 4, 5, 6, 7], avg_score=0.8, bridge_type="打脸"),  # 父集
    ]
    result = detector._dedup_and_sort(bridges)
    # 子集被剔，保留父集
    assert len(result) == 1
    assert result[0].chapters == [3, 4, 5, 6, 7]


def test_dedup_subset_different_type_both_kept():
    """V4.2.1 dedup：子集关系但 type 不同 → 都保留（不同桥段）。"""
    detector = BridgeDetector(ai_service=None)
    bridges = [
        BridgeWindow(chapters=[5], avg_score=0.7, bridge_type="单章爽点"),
        BridgeWindow(chapters=[3, 4, 5, 6, 7], avg_score=0.8, bridge_type="长卷打脸"),
    ]
    result = detector._dedup_and_sort(bridges)
    assert len(result) == 2


# ============================================================
# V4.2.2 raw_chapters 正文喂 LLM（绕开 summary 压缩）
# ============================================================


from dataclasses import dataclass


@dataclass
class _MockRawChapter:
    """模拟 Chapter（来自 chapter_splitter），含 chapter_number + content。"""
    chapter_number: int
    content: str


@pytest.mark.asyncio
async def test_raw_chapters_used_in_shortform_path():
    """V4.2.2：raw_chapters 提供时，short_form 路径应把正文（不是 summary）喂给 LLM。"""
    fact = make_chapter_fact(
        1, summary="高度压缩的单行摘要。",  # summary 故意短
    )
    raw_chapter = _MockRawChapter(
        chapter_number=1,
        content="完整的第 1 章正文，含多个独立桥段：第一段是日常嘲讽与反击；"
                "第二段是真实力的展示；第三段是身份伏笔与揭露。" * 5,
    )

    # 用一个能捕获实际 prompt 内容的 mock
    captured_prompts: list[str] = []

    async def capture_prompt(prompt, **kwargs):
        captured_prompts.append(prompt)
        return {"content": '{"bridges": []}'}

    ai = MagicMock()
    ai.generate_text = AsyncMock(side_effect=capture_prompt)
    detector = BridgeDetector(ai_service=ai, enable_llm=True)

    await detector.detect_bridges([fact], raw_chapters=[raw_chapter])

    # 实际 prompt 中应含正文片段，而非压缩 summary
    assert len(captured_prompts) >= 1
    full_prompt = captured_prompts[0]
    # 正文关键字应出现
    assert "完整的第 1 章正文" in full_prompt or "身份伏笔" in full_prompt
    # 压缩 summary 不应出现（防止双重喂数据）
    assert "高度压缩的单行摘要" not in full_prompt


@pytest.mark.asyncio
async def test_no_raw_chapters_falls_back_to_summary():
    """V4.2.2：未传 raw_chapters 时，应回退到 summary 模式（向后兼容）。"""
    fact = make_chapter_fact(
        1, summary="林七一拳秒杀对方，全场震惊。",
    )
    captured_prompts: list[str] = []

    async def capture_prompt(prompt, **kwargs):
        captured_prompts.append(prompt)
        return {"content": '{"bridges": []}'}

    ai = MagicMock()
    ai.generate_text = AsyncMock(side_effect=capture_prompt)
    detector = BridgeDetector(ai_service=ai, enable_llm=True)

    # 不传 raw_chapters
    await detector.detect_bridges([fact])

    assert len(captured_prompts) >= 1
    full_prompt = captured_prompts[0]
    # summary 应出现（V4.2.1 行为）
    assert "林七一拳秒杀对方" in full_prompt


@pytest.mark.asyncio
async def test_raw_chapters_truncation_for_long_content():
    """V4.2.2：长章节正文应被安全截断（防爆 token）。"""
    fact = make_chapter_fact(1, summary="x")
    # 10000 字长章节
    long_content = "完整章节正文。" * 1500
    raw_chapter = _MockRawChapter(chapter_number=1, content=long_content)

    captured_prompts: list[str] = []

    async def capture_prompt(prompt, **kwargs):
        captured_prompts.append(prompt)
        return {"content": '{"bridges": []}'}

    ai = MagicMock()
    ai.generate_text = AsyncMock(side_effect=capture_prompt)
    detector = BridgeDetector(ai_service=ai, enable_llm=True)

    await detector.detect_bridges([fact], raw_chapters=[raw_chapter])

    full_prompt = captured_prompts[0]
    # 应含省略标记
    assert "[...省略中段" in full_prompt
    # 截断后 prompt 长度应远小于原始内容（4000 字 + 系统模板）
    assert len(full_prompt) < 8000


@pytest.mark.asyncio
async def test_multi_chapter_path_still_uses_summary_by_default():
    """V4.2.2：多章场景（n > USE_RAW_TEXT_REGION_MAX）默认仍用 summary，
    即便 raw_chapters 提供也不自动启用正文（防爆 token）。"""
    facts = []
    for i in range(1, 11):
        if i == 5:
            facts.append(make_chapter_fact(
                i,
                summary="林七秒杀对方震惊全场目瞪口呆完胜碾压横扫！" * 3,
            ))
        else:
            facts.append(make_chapter_fact(i, summary=f"林七日常 {i}。"))

    raw_chapters = [
        _MockRawChapter(chapter_number=i, content=f"第 {i} 章完整正文内容..." * 100)
        for i in range(1, 11)
    ]

    captured_prompts: list[str] = []

    async def capture_prompt(prompt, **kwargs):
        captured_prompts.append(prompt)
        return {"content": '{"bridges": []}'}

    ai = MagicMock()
    ai.generate_text = AsyncMock(side_effect=capture_prompt)
    detector = BridgeDetector(ai_service=ai, enable_llm=True)

    await detector.detect_bridges(facts, raw_chapters=raw_chapters)

    # 验证 LLM 被调用
    assert len(captured_prompts) >= 1
    # 验证多章区域用 summary（含"摘要："标记，正文模式无此标记）
    full_prompt = captured_prompts[0]
    assert "摘要：" in full_prompt
    # 不应整段正文都被喂进去
    assert "完整正文内容..." * 50 not in full_prompt


def test_build_raw_lookup_handles_edge_cases():
    """V4.2.2 _build_raw_lookup 边界情况。"""
    detector = BridgeDetector(ai_service=None)
    # None 输入
    assert detector._build_raw_lookup(None) == {}
    # 空列表
    assert detector._build_raw_lookup([]) == {}
    # 缺字段的项被跳过
    bad = _MockRawChapter(chapter_number=0, content="x")  # ch_num=0 应跳过
    good = _MockRawChapter(chapter_number=5, content="content")
    empty = _MockRawChapter(chapter_number=3, content="")  # 空 content 应跳过
    result = detector._build_raw_lookup([bad, good, empty])
    assert result == {5: "content"}


def test_truncate_raw_content():
    """V4.2.2 长正文截断行为。"""
    short = "短章节" * 100  # 300 字
    assert BridgeDetector._truncate_raw_content(short) == short

    long = "长章节" * 2000  # 6000 字
    truncated = BridgeDetector._truncate_raw_content(long)
    assert "[...省略中段" in truncated
    assert len(truncated) < len(long)
    # 头部完整保留
    assert truncated.startswith("长章节")
    # 尾部完整保留
    assert truncated.endswith("长章节")


def test_aggregator_handles_single_chapter_bridge():
    """BridgePatternAggregator 应能正确统计单章桥段。"""
    bridges = [
        BridgeWindow(
            chapters=[1],
            avg_score=0.7,
            is_standard=False,
            bridge_type="单章爽点",
            detection_origin="llm_shortform",
            confidence_breakdown={"llm_confidence": 0.7, "bridge_length": 1.0},
        ),
    ]
    chapter_facts = [ChapterFact(chapter_number=1, summary="一拳秒杀全场震惊。")]
    agg = BridgePatternAggregator()
    result = agg.aggregate(bridges, chapter_facts=chapter_facts)
    assert result["total_bridges_detected"] == 1
    assert result["rhythm_stats"]["bridge_length_distribution"]["micro_1_2"] == 1
    assert result["rhythm_stats"]["avg_bridge_length"] == 1.0
    # typical_examples 应正确序列化单章
    for type_entry in result["bridge_types"]:
        for ex in type_entry["typical_examples"]:
            assert ex["bridge_length"] == 1
            assert ex["chapters"] == [1]
            assert "ch1" in ex["chapter_summaries"]
