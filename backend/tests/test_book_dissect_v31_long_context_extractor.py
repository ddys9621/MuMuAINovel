"""拆书 V3.1 LongContextExtractor 验收测试。

覆盖：
- 主流程：mock LLM 返回完整 chapters → 正确解析为 ChapterFact 列表
- 漏章兜底：LLM 漏给中间章节 → 空 ChapterFact 占位
- 顺序保护：LLM 乱序返回 → 输出按 chapter_number 升序
- 失败链：LLM 调用异常 / 空 content / 非 JSON / chapters 非 list / 全空覆盖
- max_tokens 动态计算
- 边界标记拼接

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.chapter_splitter import Chapter
from app.services.book_dissect.long_context_extractor import (
    LongContextExtractionError,
    LongContextExtractor,
)
from app.services.book_dissect.v2_types import ChapterFact


# ============================================================
# fixtures
# ============================================================


def make_chapters(count: int) -> list[Chapter]:
    return [
        Chapter(
            chapter_number=i + 1,
            title=f"第{i+1}章",
            raw_title=f"第{i+1}章",
            content=f"第 {i+1} 章正文内容，包含林七的故事。" * 10,
            word_count=200,
            kind="chapter",
        )
        for i in range(count)
    ]


def make_fact_dict(num: int, *, summary: str = None, with_chars: bool = False) -> dict:
    """构造一个 LLM 返回的单章 dict。"""
    out = {
        "chapter_number": num,
        "chapter_title": f"第{num}章",
        "summary": summary or f"本章摘要 {num}",
        "characters": [],
        "relationships": [],
        "locations": [],
        "events": [],
        "item_events": [],
        "org_events": [],
        "new_concepts": [],
    }
    if with_chars:
        out["characters"] = [{
            "name": "林七",
            "new_aliases": [],
            "role_hint": "protagonist",
            "appearance": "瘦削少年",
            "abilities_gained": [],
            "locations_in_chapter": [],
            "evidence": "林七出场",
        }]
    return out


def mock_llm(json_obj: dict | str | Exception) -> MagicMock:
    ai = MagicMock()
    if isinstance(json_obj, Exception):
        ai.generate_text = AsyncMock(side_effect=json_obj)
    else:
        content = json.dumps(json_obj, ensure_ascii=False) if isinstance(json_obj, dict) else json_obj
        ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


# ============================================================
# 主流程
# ============================================================


class TestExtractAllSuccess:
    @pytest.mark.asyncio
    async def test_normal_full_extraction(self):
        chapters = make_chapters(3)
        ai = mock_llm({
            "chapters": [
                make_fact_dict(1, summary="开篇林七觉醒", with_chars=True),
                make_fact_dict(2, summary="拜入青云宗"),
                make_fact_dict(3, summary="初次对战"),
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert len(facts) == 3
        assert all(isinstance(f, ChapterFact) for f in facts)
        assert facts[0].summary == "开篇林七觉醒"
        assert facts[0].characters[0].name == "林七"
        assert facts[0].characters[0].role_hint == "protagonist"
        ai.generate_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chapter_title_fallback_from_input(self):
        """LLM 漏给 chapter_title 时应从输入章节兜底。"""
        chapters = make_chapters(1)
        ai = mock_llm({
            "chapters": [
                {
                    "chapter_number": 1,
                    "chapter_title": "",   # 故意留空
                    "summary": "测试",
                    "characters": [], "relationships": [], "locations": [],
                    "events": [], "item_events": [], "org_events": [], "new_concepts": [],
                }
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert facts[0].chapter_title == "第1章"

    @pytest.mark.asyncio
    async def test_chapter_count_one(self):
        """边界：仅 1 章也能跑（虽然 router 会拦截 < MIN_CHAPTERS_FOR_LC，
        但本模块本身不做章节数校验）。"""
        chapters = make_chapters(1)
        ai = mock_llm({"chapters": [make_fact_dict(1)]})
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert len(facts) == 1


class TestExtractAllOrdering:
    @pytest.mark.asyncio
    async def test_llm_out_of_order_resorted(self):
        """LLM 乱序返回 → 输出按 chapter_number 升序。"""
        chapters = make_chapters(3)
        ai = mock_llm({
            "chapters": [
                make_fact_dict(3, summary="C"),
                make_fact_dict(1, summary="A"),
                make_fact_dict(2, summary="B"),
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert [f.chapter_number for f in facts] == [1, 2, 3]
        assert [f.summary for f in facts] == ["A", "B", "C"]


class TestExtractAllPartial:
    @pytest.mark.asyncio
    async def test_missing_middle_chapter_filled_empty(self):
        """LLM 漏给中间章节 → 空 ChapterFact 占位 + 输出长度等于输入。"""
        chapters = make_chapters(3)
        ai = mock_llm({
            "chapters": [
                make_fact_dict(1, summary="A"),
                # 漏 2
                make_fact_dict(3, summary="C", with_chars=True),
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert len(facts) == 3
        assert facts[0].summary == "A"
        # 漏的章节应是空 ChapterFact 但保留 chapter_number / chapter_title
        assert facts[1].chapter_number == 2
        assert facts[1].chapter_title == "第2章"
        assert facts[1].summary is None
        assert facts[1].characters == []
        assert facts[2].summary == "C"

    @pytest.mark.asyncio
    async def test_extra_unknown_chapter_ignored(self):
        """LLM 多给一个不存在的章节号 → 忽略（输出仅含输入章节）。"""
        chapters = make_chapters(2)
        ai = mock_llm({
            "chapters": [
                make_fact_dict(1, summary="A"),
                make_fact_dict(2, summary="B"),
                make_fact_dict(99, summary="不存在的章"),
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert len(facts) == 2
        assert {f.chapter_number for f in facts} == {1, 2}

    @pytest.mark.asyncio
    async def test_invalid_chapter_number_skipped(self):
        """非整数 chapter_number 应被跳过。"""
        chapters = make_chapters(2)
        ai = mock_llm({
            "chapters": [
                {"chapter_number": "abc", "summary": "..."},  # 非整数
                make_fact_dict(1, summary="A"),
                make_fact_dict(2, summary="B"),
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all(chapters)
        assert len(facts) == 2


class TestExtractAllFailures:
    @pytest.mark.asyncio
    async def test_llm_call_exception(self):
        ai = mock_llm(RuntimeError("API down"))
        extractor = LongContextExtractor(ai_service=ai)
        with pytest.raises(LongContextExtractionError):
            await extractor.extract_all(make_chapters(3))

    @pytest.mark.asyncio
    async def test_empty_content(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": ""})
        extractor = LongContextExtractor(ai_service=ai)
        with pytest.raises(LongContextExtractionError):
            await extractor.extract_all(make_chapters(3))

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        ai = mock_llm("not a json {{ broken")
        extractor = LongContextExtractor(ai_service=ai)
        with pytest.raises(LongContextExtractionError):
            await extractor.extract_all(make_chapters(3))

    @pytest.mark.asyncio
    async def test_missing_chapters_field(self):
        """LLM 返回 dict 但缺 chapters 字段 → 抛错。"""
        ai = mock_llm({"foo": "bar"})
        extractor = LongContextExtractor(ai_service=ai)
        with pytest.raises(LongContextExtractionError):
            await extractor.extract_all(make_chapters(3))

    @pytest.mark.asyncio
    async def test_chapters_not_list(self):
        ai = mock_llm({"chapters": "not a list"})
        extractor = LongContextExtractor(ai_service=ai)
        with pytest.raises(LongContextExtractionError):
            await extractor.extract_all(make_chapters(3))

    @pytest.mark.asyncio
    async def test_all_chapters_empty_yields_error(self):
        """所有章节都解析为空 ChapterFact → 抛错（聚合无意义）。"""
        chapters = make_chapters(3)
        ai = mock_llm({
            "chapters": [
                {"chapter_number": 1, "characters": [], "events": [], "locations": []},
                {"chapter_number": 2, "characters": [], "events": [], "locations": []},
                {"chapter_number": 3, "characters": [], "events": [], "locations": []},
            ]
        })
        extractor = LongContextExtractor(ai_service=ai)
        with pytest.raises(LongContextExtractionError):
            await extractor.extract_all(chapters)

    @pytest.mark.asyncio
    async def test_empty_chapters_returns_empty(self):
        """输入空章节直接返回空（不调 LLM）。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock()
        extractor = LongContextExtractor(ai_service=ai)
        facts = await extractor.extract_all([])
        assert facts == []
        ai.generate_text.assert_not_called()


class TestComputeMaxTokens:
    def test_base_for_few_chapters(self):
        extractor = LongContextExtractor(ai_service=MagicMock())
        # 5 章 → 16000 + 5*600 = 19000
        assert extractor._compute_max_tokens(5) == 19_000

    def test_capped_at_hard_limit(self):
        extractor = LongContextExtractor(ai_service=MagicMock())
        # 1000 章 → 16000 + 600000 = 616000，应被压到 64000
        assert extractor._compute_max_tokens(1000) == 64_000


class TestBuildFullText:
    def test_includes_boundary_markers(self):
        extractor = LongContextExtractor(ai_service=MagicMock())
        chapters = make_chapters(3)
        text = extractor._build_full_text(chapters)
        # 每章应有边界标记
        for i in range(1, 4):
            assert f"=== 第 {i} 章" in text

    def test_empty_content_chapter_still_has_boundary(self):
        """空内容章节也应保留边界标记。"""
        extractor = LongContextExtractor(ai_service=MagicMock())
        chapters = [
            Chapter(chapter_number=1, title="序", raw_title="序", content="",
                    word_count=0, kind="preamble"),
            Chapter(chapter_number=2, title="第二章", raw_title="第二章",
                    content="正文", word_count=2, kind="chapter"),
        ]
        text = extractor._build_full_text(chapters)
        assert "=== 第 1 章 序 ===" in text
        assert "=== 第 2 章 第二章 ===" in text
        assert "正文" in text
