"""T2.3: ChapterFactExtractor 段级切半重试测试。

覆盖：
- 首次成功 → 不切半
- 段长度 < MIN_RETRY_SPLIT_LEN → 不切半，直接放弃
- 段长度足够 + 首次失败（异常） → 切半 → 1 子段成功 → 返回 merged
- 段长度足够 + 首次失败（异常） → 切半 → 全部子段失败 → 返回空 fact
- 段长度足够 + 首次返回空 content → 切半重试
- 段长度足够 + 首次返回非 JSON → 切半重试
- _split_segment_half 边界（极短文本不切）
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.chapter_fact_extractor import ChapterFactExtractor
from app.services.book_dissect.v2_types import ChapterFact


# ============================================================
# helpers
# ============================================================


def _segment_text(length: int) -> str:
    """构造指定字符长度的段落文本（带 \\n 边界）。"""
    para = "这是测试段落内容，用于模拟章节抽取场景。\n"  # 22 字符
    n = (length // len(para)) + 1
    return (para * n)[:length]


def _make_ai_with_responses(responses: list):
    """构造 mock AIService，generate_text 按 responses 顺序返回。

    responses 元素：
    - dict {"content": "..."} → 返回该 dict
    - Exception → raise
    - "" → 返回 {"content": ""}（空 content）
    - str → 返回 {"content": str}
    """
    ai = MagicMock()
    call_results = []
    for r in responses:
        if isinstance(r, BaseException):
            call_results.append(r)
        elif isinstance(r, dict):
            call_results.append(r)
        else:
            call_results.append({"content": str(r)})

    async def _generate(*args, **kwargs):
        if not call_results:
            raise RuntimeError("mock 已用完")
        r = call_results.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r

    ai.generate_text = AsyncMock(side_effect=_generate)
    return ai


def _make_valid_chapter_fact_json(summary: str = "测试摘要") -> str:
    """构造合法的 ChapterFact JSON 字符串。"""
    return json.dumps({
        "summary": summary,
        "characters": [],
        "relationships": [],
        "locations": [],
        "events": [],
        "item_events": [],
        "org_events": [],
        "new_concepts": [],
    }, ensure_ascii=False)


# ============================================================
# 正常成功路径
# ============================================================


@pytest.mark.asyncio
async def test_segment_success_no_split_retry():
    """段首次成功 → 不触发切半。"""
    ai = _make_ai_with_responses([_make_valid_chapter_fact_json("正常摘要")])
    extractor = ChapterFactExtractor(ai_service=ai)

    text = _segment_text(3000)  # > MIN_RETRY_SPLIT_LEN
    fact, ok = await extractor._extract_with_split_retry(
        segment_label="1",
        chapter_number=1,
        chapter_title="测试章",
        segment_text=text,
        dictionary=[],
        prior_summary=None,
    )

    assert ok is True
    assert fact.summary == "正常摘要"
    assert ai.generate_text.call_count == 1


# ============================================================
# 段太短，跳过切半
# ============================================================


@pytest.mark.asyncio
async def test_segment_fail_too_short_no_split():
    """段长度 < MIN_RETRY_SPLIT_LEN → 失败时不切半。"""
    ai = _make_ai_with_responses([RuntimeError("LLM 异常")])
    extractor = ChapterFactExtractor(ai_service=ai)

    short_text = _segment_text(1000)  # < 2000
    fact, ok = await extractor._extract_with_split_retry(
        segment_label="1",
        chapter_number=1,
        chapter_title="测试章",
        segment_text=short_text,
        dictionary=[],
        prior_summary=None,
    )

    assert ok is False
    assert not fact.summary  # 默认 None 或空字符串
    assert ai.generate_text.call_count == 1  # 只调一次，不切半


# ============================================================
# 段足够长 + 异常失败 → 切半 → 1 半成功
# ============================================================


@pytest.mark.asyncio
async def test_segment_exception_split_one_half_succeeds():
    """异常失败 → 切半 → 子段 1 成功 → 返回 merged。"""
    ai = _make_ai_with_responses([
        RuntimeError("首次 LLM 异常"),         # 原段失败
        _make_valid_chapter_fact_json("前半摘要"),  # 子段 1 成功
        RuntimeError("子段 2 LLM 异常"),       # 子段 2 失败
    ])
    extractor = ChapterFactExtractor(ai_service=ai)

    long_text = _segment_text(4000)
    fact, ok = await extractor._extract_with_split_retry(
        segment_label="1.3/3",
        chapter_number=1,
        chapter_title="测试章",
        segment_text=long_text,
        dictionary=[],
        prior_summary=None,
    )

    assert ok is True
    assert "前半摘要" in (fact.summary or "")
    assert ai.generate_text.call_count == 3  # 原段 + 2 子段


# ============================================================
# 段足够长 + 空 content 失败 → 切半 → 两半都成功
# ============================================================


@pytest.mark.asyncio
async def test_segment_empty_content_split_both_halves_succeed():
    """空 content 失败 → 切半 → 两半都成功 → 合并 summary。"""
    ai = _make_ai_with_responses([
        {"content": ""},  # 原段返回空
        _make_valid_chapter_fact_json("前半"),
        _make_valid_chapter_fact_json("后半"),
    ])
    extractor = ChapterFactExtractor(ai_service=ai)

    long_text = _segment_text(5000)
    fact, ok = await extractor._extract_with_split_retry(
        segment_label="1.2/2",
        chapter_number=1,
        chapter_title="测试章",
        segment_text=long_text,
        dictionary=[],
        prior_summary=None,
    )

    assert ok is True
    # 合并后 summary 应包含两个子段的内容
    summary = fact.summary or ""
    assert "前半" in summary
    assert "后半" in summary
    assert ai.generate_text.call_count == 3


# ============================================================
# 段足够长 + 非 JSON 失败 → 切半重试
# ============================================================


@pytest.mark.asyncio
async def test_segment_invalid_json_split_retry():
    """非 JSON 内容失败 → 切半 → 子段成功。"""
    ai = _make_ai_with_responses([
        {"content": "这不是 JSON，就是一段纯文本"},  # JSON 解析失败
        _make_valid_chapter_fact_json("子段 1"),
        _make_valid_chapter_fact_json("子段 2"),
    ])
    extractor = ChapterFactExtractor(ai_service=ai)

    long_text = _segment_text(3500)
    fact, ok = await extractor._extract_with_split_retry(
        segment_label="1",
        chapter_number=1,
        chapter_title="测试章",
        segment_text=long_text,
        dictionary=[],
        prior_summary=None,
    )

    assert ok is True
    assert ai.generate_text.call_count == 3


# ============================================================
# 段足够长 + 全部子段失败
# ============================================================


@pytest.mark.asyncio
async def test_segment_split_all_halves_fail_returns_empty():
    """切半重试全部失败 → 返回原空 fact，ok=False。"""
    ai = _make_ai_with_responses([
        RuntimeError("原段失败"),
        RuntimeError("子段 1 失败"),
        RuntimeError("子段 2 失败"),
    ])
    extractor = ChapterFactExtractor(ai_service=ai)

    long_text = _segment_text(4000)
    fact, ok = await extractor._extract_with_split_retry(
        segment_label="1",
        chapter_number=1,
        chapter_title="测试章",
        segment_text=long_text,
        dictionary=[],
        prior_summary=None,
    )

    assert ok is False
    assert not fact.summary  # 原 fact 是空（None 或 ""）
    assert ai.generate_text.call_count == 3  # 原段 + 2 子段都试了


# ============================================================
# _split_segment_half 边界
# ============================================================


def test_split_segment_half_very_short_text():
    """极短文本（<200 字）原样返回不切。"""
    halves = ChapterFactExtractor._split_segment_half("短文本")
    assert halves == ["短文本"]


def test_split_segment_half_exactly_200():
    """边界 200 字 → 切两半。"""
    text = "x" * 200
    halves = ChapterFactExtractor._split_segment_half(text)
    assert len(halves) == 2
    assert sum(len(h) for h in halves) == 200


def test_split_segment_half_normal_text_preserves_total_length():
    """正常长度切两半 → 字符总数不变。"""
    text = "段落\n" * 100  # 300 字
    halves = ChapterFactExtractor._split_segment_half(text)
    assert len(halves) == 2
    assert sum(len(h) for h in halves) == len(text)
    # 切点应该是段落边界（以 \n 结束的子串）
    assert halves[0].endswith("\n")


def test_split_segment_half_no_newline_falls_back_to_hard_split():
    """无换行符的长文本 → 退化到硬中点切。"""
    text = "a" * 1000  # 无 \n
    halves = ChapterFactExtractor._split_segment_half(text)
    assert len(halves) == 2
    assert sum(len(h) for h in halves) == 1000


# ============================================================
# 端到端：extract() 主入口验证切半重试集成
# ============================================================


@pytest.mark.asyncio
async def test_extract_chapter_one_segment_fails_split_recovers():
    """extract() 主入口：单段超长章首次失败 → 切半 → 一半成功 → 整章 ok。"""
    ai = _make_ai_with_responses([
        RuntimeError("原段失败"),
        _make_valid_chapter_fact_json("恢复段摘要"),
        {"content": ""},  # 第 2 子段失败也没关系
    ])
    extractor = ChapterFactExtractor(ai_service=ai)

    # 长度 < SEGMENT_THRESHOLD_2，所以只切 1 段；这 1 段够长（>MIN_RETRY_SPLIT_LEN）
    chapter_text = _segment_text(5000)
    fact = await extractor.extract(
        chapter_number=1,
        chapter_title="测试章",
        chapter_text=chapter_text,
        dictionary=[],
        prior_summary=None,
    )

    # 应该没有抛出 ChapterExtractionError（因为切半救回来了）
    assert fact.chapter_number == 1
    assert "恢复段摘要" in (fact.summary or "")
    assert ai.generate_text.call_count == 3  # 原段 + 2 子段


@pytest.mark.asyncio
async def test_extract_chapter_one_segment_split_all_fail_raises():
    """extract() 主入口：所有段（含切半）都失败 → 抛 ChapterExtractionError。"""
    from app.services.book_dissect.chapter_fact_extractor import (
        ChapterExtractionError,
    )

    ai = _make_ai_with_responses([
        RuntimeError("原段失败"),
        RuntimeError("子段 1 失败"),
        RuntimeError("子段 2 失败"),
    ])
    extractor = ChapterFactExtractor(ai_service=ai)

    chapter_text = _segment_text(5000)  # < SEGMENT_THRESHOLD_2，只 1 段
    with pytest.raises(ChapterExtractionError):
        await extractor.extract(
            chapter_number=1,
            chapter_title="测试章",
            chapter_text=chapter_text,
            dictionary=[],
            prior_summary=None,
        )
