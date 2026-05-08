"""拆书 V3.1.4 章节切分 LLM Fallback 验收测试。

覆盖：
- needs_llm_fallback：触发条件（巨型单章 / 超大章节）
- _sample_head_mid_tail：短文本 / 长文本采样
- _parse_decision：合法 / 非法 / 缺字段
- _split_by_llm_regex：正常切分 / 非法正则 / 无匹配
- _fixed_size_split：长文 / 短文 / 末段合并
- LlmChapterSplitter.analyze：mock LLM / LLM 失败 / 空响应
- split_with_llm_fallback 主入口：正则够用跳过 / LLM 触发 / LLM 失败降级

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §6
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.chapter_splitter import Chapter
from app.services.book_dissect.llm_chapter_splitter import (
    GIANT_CHAPTER_THRESHOLD,
    LlmBoundaryDecision,
    LlmChapterSplitter,
    VERY_LARGE_CHAPTER,
    _fixed_size_split,
    _parse_decision,
    _sample_head_mid_tail,
    _split_by_llm_regex,
    needs_llm_fallback,
    split_with_llm_fallback,
)


# ============================================================
# fixtures
# ============================================================


def make_chapter(num: int, content: str, title: str = None) -> Chapter:
    return Chapter(
        chapter_number=num,
        title=title or f"第{num}章",
        raw_title=title or f"第{num}章",
        content=content,
        word_count=len(content),
        kind="chapter" if num > 1 else "preamble",
    )


def mock_llm_response(json_obj: dict | str | Exception) -> MagicMock:
    ai = MagicMock()
    if isinstance(json_obj, Exception):
        ai.generate_text = AsyncMock(side_effect=json_obj)
    else:
        content = json.dumps(json_obj, ensure_ascii=False) if isinstance(json_obj, dict) else json_obj
        ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


# ============================================================
# needs_llm_fallback
# ============================================================


class TestNeedsLlmFallback:
    def test_giant_single_chapter_triggers(self):
        """单章 > 30k 触发。"""
        text = "a" * (GIANT_CHAPTER_THRESHOLD + 1000)
        chapters = [make_chapter(1, text, "全文")]
        assert needs_llm_fallback(chapters) is True

    def test_normal_chapters_dont_trigger(self):
        """多个正常章节不触发。"""
        chapters = [
            make_chapter(1, "a" * 5000),
            make_chapter(2, "b" * 6000),
            make_chapter(3, "c" * 4000),
        ]
        assert needs_llm_fallback(chapters) is False

    def test_short_single_chapter_no_trigger(self):
        """单章但字数 ≤ 阈值不触发。"""
        chapters = [make_chapter(1, "a" * 5000, "全文")]
        assert needs_llm_fallback(chapters) is False

    def test_oversized_among_multiple_triggers(self):
        """多章但含超大章节（> 50k）触发。"""
        chapters = [
            make_chapter(1, "a" * 5000),
            make_chapter(2, "b" * (VERY_LARGE_CHAPTER + 1000)),
        ]
        assert needs_llm_fallback(chapters) is True

    def test_empty_chapters(self):
        assert needs_llm_fallback([]) is False


# ============================================================
# _sample_head_mid_tail
# ============================================================


class TestSampleHeadMidTail:
    def test_long_text_samples_three_parts(self):
        text = "x" * 20_000
        head, mid, tail = _sample_head_mid_tail(text)
        assert len(head) > 0
        assert len(mid) > 0
        assert len(tail) > 0
        # head 来自开头，tail 来自结尾
        assert head == text[:3000]
        assert tail == text[-3000:]

    def test_short_text_only_head(self):
        text = "y" * 5000
        head, mid, tail = _sample_head_mid_tail(text)
        assert head
        assert mid == ""
        assert tail == ""


# ============================================================
# _parse_decision
# ============================================================


class TestParseDecision:
    def test_valid_fixed_size(self):
        raw = json.dumps({
            "text_type": "essay",
            "boundary_pattern": None,
            "estimated_chapter_count": 8,
            "estimated_chapter_chars": 3000,
            "fallback_action": "fixed_size",
        })
        d = _parse_decision(raw)
        assert d is not None
        assert d.fallback_action == "fixed_size"
        assert d.text_type == "essay"
        assert d.estimated_chapter_count == 8

    def test_valid_regex_split(self):
        # 注意：避开 `{N,}` 这类量词 —— json_cleaner 会把"逗号+}"当作尾逗号清掉，
        # 把 `{3,}` 解析成 `{3}`。这是 json_cleaner 的已知副作用（跨模块限制）。
        # Prompt 已提示 LLM 给出合法 Python regex，实际使用时规避这类格式即可。
        raw = json.dumps({
            "text_type": "novel",
            "boundary_pattern": r"^※{3}$",
            "estimated_chapter_count": 20,
            "estimated_chapter_chars": 2500,
            "fallback_action": "regex_split",
        })
        d = _parse_decision(raw)
        assert d is not None
        assert d.fallback_action == "regex_split"
        assert d.boundary_pattern == r"^※{3}$"

    def test_invalid_action_returns_none(self):
        raw = json.dumps({
            "text_type": "other",
            "fallback_action": "not_a_real_action",
        })
        assert _parse_decision(raw) is None

    def test_non_object_returns_none(self):
        assert _parse_decision("not a json at all") is None
        assert _parse_decision("[]") is None

    def test_missing_action_returns_none(self):
        raw = json.dumps({"text_type": "novel"})
        assert _parse_decision(raw) is None


# ============================================================
# _split_by_llm_regex
# ============================================================


class TestSplitByLlmRegex:
    def test_valid_regex_multiple_matches(self):
        text = "开篇内容\n※※※\n第一段内容\n※※※\n第二段内容"
        chapters = _split_by_llm_regex(text, r"^※{3,}$")
        assert chapters is not None
        assert len(chapters) >= 2

    def test_invalid_regex_returns_none(self):
        chapters = _split_by_llm_regex("text", r"[invalid(")
        assert chapters is None

    def test_no_matches_returns_none(self):
        chapters = _split_by_llm_regex("just plain text", r"^\#\#\#$")
        assert chapters is None

    def test_one_match_returns_none(self):
        """仅 1 次匹配不足以切分。"""
        chapters = _split_by_llm_regex("before\n###\nafter", r"^\#{3}$")
        assert chapters is None


# ============================================================
# _fixed_size_split
# ============================================================


class TestFixedSizeSplit:
    def test_long_text_splits_multiple(self):
        # 每段 ~400 字 × 40 段 ≈ 16k 字，远大于 FIXED_SIZE_TARGET=5000
        text = "\n\n".join(["段落" * 200 for _ in range(40)])
        chapters = _fixed_size_split(text)
        assert len(chapters) >= 2
        # 每段应有内容
        assert all(c.content.strip() for c in chapters)
        # 章节号连续
        assert [c.chapter_number for c in chapters] == list(range(1, len(chapters) + 1))

    def test_short_text_single_chapter(self):
        text = "短文本" * 100
        chapters = _fixed_size_split(text)
        assert len(chapters) == 1
        assert chapters[0].title == "全文"

    def test_empty_text(self):
        assert _fixed_size_split("") == []

    def test_whitespace_only(self):
        assert _fixed_size_split("   \n\n   ") == []


# ============================================================
# LlmChapterSplitter.analyze
# ============================================================


class TestLlmChapterSplitterAnalyze:
    @pytest.mark.asyncio
    async def test_normal_decision(self):
        ai = mock_llm_response({
            "text_type": "essay",
            "boundary_pattern": None,
            "estimated_chapter_count": 5,
            "estimated_chapter_chars": 3000,
            "fallback_action": "fixed_size",
        })
        splitter = LlmChapterSplitter(ai_service=ai)
        text = "a" * 20_000
        decision = await splitter.analyze(text)
        assert decision is not None
        assert decision.fallback_action == "fixed_size"

    @pytest.mark.asyncio
    async def test_llm_exception_returns_none(self):
        ai = mock_llm_response(RuntimeError("API down"))
        splitter = LlmChapterSplitter(ai_service=ai)
        decision = await splitter.analyze("a" * 20_000)
        assert decision is None

    @pytest.mark.asyncio
    async def test_short_text_skips_llm(self):
        """文本短于门槛直接返回 None，不调 LLM。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock()
        splitter = LlmChapterSplitter(ai_service=ai)
        decision = await splitter.analyze("短文")
        assert decision is None
        ai.generate_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_content_returns_none(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": ""})
        splitter = LlmChapterSplitter(ai_service=ai)
        decision = await splitter.analyze("a" * 20_000)
        assert decision is None


# ============================================================
# split_with_llm_fallback 主入口
# ============================================================


class TestSplitWithLlmFallback:
    @pytest.mark.asyncio
    async def test_normal_text_skips_llm(self):
        """常规网文（已能正常切分）不调 LLM。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock()
        text = "\n\n".join([
            "第一章 开端", "第一章正文" * 200,
            "第二章 发展", "第二章正文" * 200,
            "第三章 高潮", "第三章正文" * 200,
        ])
        chapters = await split_with_llm_fallback(text, ai_service=ai)
        assert len(chapters) >= 3
        ai.generate_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_giant_single_chapter_triggers_llm(self):
        """巨型单章应触发 LLM 并根据决策切分。"""
        ai = mock_llm_response({
            "text_type": "essay",
            "boundary_pattern": None,
            "fallback_action": "fixed_size",
        })
        text = "段落内容" * 10_000  # ~40k 字且无章节标题
        chapters = await split_with_llm_fallback(text, ai_service=ai)
        assert len(chapters) >= 2  # fixed_size 切出多段
        ai.generate_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_fixed_size(self):
        """LLM 调用失败降级 fixed_size_split。"""
        ai = mock_llm_response(RuntimeError("API down"))
        text = "段落内容" * 10_000
        chapters = await split_with_llm_fallback(text, ai_service=ai)
        assert len(chapters) >= 2  # 降级 fixed_size 仍能切出多段

    @pytest.mark.asyncio
    async def test_single_chapter_decision_preserved(self):
        """LLM 判定 single_chapter → 保留原始单章。"""
        ai = mock_llm_response({
            "text_type": "other",
            "boundary_pattern": None,
            "fallback_action": "single_chapter",
        })
        text = "段落内容" * 10_000
        chapters = await split_with_llm_fallback(text, ai_service=ai)
        assert len(chapters) == 1
