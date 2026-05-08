"""拆书 V2 Phase 4 验收测试

覆盖：
- SummaryBuilder（前章摘要）
- FactValidator（形态学过滤 + 字典驱动修正 + 别名链合并）
- ChapterFactExtractor（长章节切分 + LLM 调用 + JSON 解析 + 多段合并）
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.chapter_fact_extractor import (
    ChapterExtractionError,
    ChapterFactExtractor,
)
from app.services.book_dissect.fact_validator import FactValidator
from app.services.book_dissect.summary_builder import SummaryBuilder
from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    DictionaryEntry,
    EventFact,
    Importance,
    ItemFact,
    LocationFact,
    OrgFact,
    RelationFact,
)


# ============================================================
# SummaryBuilder
# ============================================================


def make_chapter_fact(num: int, summary: str = "...", chars=None, events=None, locs=None) -> ChapterFact:
    return ChapterFact(
        chapter_number=num,
        chapter_title=f"第{num}章",
        summary=summary,
        characters=chars or [],
        events=events or [],
        locations=locs or [],
    )


class TestSummaryBuilder:
    def test_empty_facts(self):
        b = SummaryBuilder()
        assert b.build([]) == ""

    def test_basic_build(self):
        b = SummaryBuilder()
        f1 = make_chapter_fact(1, "主角登场",
            chars=[CharacterFact(name="林七")],
            events=[EventFact(event_type="meet", title="初遇师父", importance="high")],
            locs=[LocationFact(name="青云宗")],
        )
        f2 = make_chapter_fact(2, "拜师入门",
            chars=[CharacterFact(name="林七"), CharacterFact(name="慕容雪")],
            events=[EventFact(event_type="join_org", title="加入青云宗", importance="high")],
        )
        text = b.build([f1, f2])
        assert "第1章" in text
        assert "第2章" in text
        assert "林七" in text
        assert "青云宗" in text
        assert "[当前活跃角色]" in text
        assert "[最近关键事件]" in text

    def test_lookback_only_recent(self):
        """只回溯 PRIOR_CHAPTERS_LOOKBACK 章。"""
        b = SummaryBuilder()
        b.PRIOR_CHAPTERS_LOOKBACK = 2
        facts = [
            make_chapter_fact(i, summary=f"摘要{i}",
                chars=[CharacterFact(name=f"角{i}")])
            for i in range(1, 6)
        ]
        text = b.build(facts)
        # 应只看到第 4-5 章
        assert "第4章" in text and "第5章" in text
        assert "第1章" not in text and "第2章" not in text

    def test_truncate_to_max(self):
        b = SummaryBuilder()
        b.MAX_SUMMARY_CHARS = 100
        # 构造超长摘要
        long_text = "一个很长的章节摘要。" * 200
        f = make_chapter_fact(1, summary=long_text)
        text = b.build([f])
        assert len(text) <= b.MAX_SUMMARY_CHARS

    def test_active_chars_sorted_by_freq(self):
        b = SummaryBuilder()
        f1 = make_chapter_fact(1, chars=[CharacterFact(name="林七"), CharacterFact(name="赵风")])
        f2 = make_chapter_fact(2, chars=[CharacterFact(name="林七")])
        f3 = make_chapter_fact(3, chars=[CharacterFact(name="林七"), CharacterFact(name="慕容雪")])
        active = b._collect_active_characters([f1, f2, f3])
        # 林七 应排第一（出场 3 次）
        assert active[0] == "林七"

    def test_high_importance_first(self):
        b = SummaryBuilder()
        f = make_chapter_fact(1, events=[
            EventFact(event_type="other", title="低优1", importance="low"),
            EventFact(event_type="other", title="高优1", importance="high"),
            EventFact(event_type="other", title="中优1", importance="medium"),
            EventFact(event_type="other", title="高优2", importance="high"),
        ])
        events = b._collect_recent_events([f], 4)
        # 前两条应是 high
        assert "高优1" in events[0]
        assert "高优2" in events[1]


# ============================================================
# FactValidator
# ============================================================


class TestFactValidator:
    def test_filter_generic_persons(self):
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[
                CharacterFact(name="林七"),
                CharacterFact(name="老者"),
                CharacterFact(name="少年"),
                CharacterFact(name="妇人"),
            ],
        )
        result = v.validate(f, dictionary=[])
        names = {c.name for c in result.characters}
        assert "林七" in names
        assert "老者" not in names
        assert "少年" not in names
        assert "妇人" not in names

    def test_filter_short_persons(self):
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[CharacterFact(name="林"), CharacterFact(name="林七")],
        )
        result = v.validate(f, dictionary=[])
        names = {c.name for c in result.characters}
        assert "林" not in names
        assert "林七" in names

    def test_filter_generic_locations(self):
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            locations=[
                LocationFact(name="青云宗"),
                LocationFact(name="山"),
                LocationFact(name="家里"),
                LocationFact(name="门口"),
            ],
        )
        result = v.validate(f, dictionary=[])
        names = {l.name for l in result.locations}
        assert "青云宗" in names
        assert "山" not in names
        assert "家里" not in names

    def test_dictionary_correction_aliases(self):
        """字典中 '林七' 有别名 '七哥'，LLM 输出 '七哥' 应被修正为 '林七'。"""
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[CharacterFact(name="七哥", abilities_gained=["御剑术"])],
            relationships=[RelationFact(person_a="七哥", person_b="慕容雪", relation_type="盟友")],
            events=[EventFact(event_type="other", title="对决", actors=["七哥"])],
        )
        dictionary = [
            DictionaryEntry(name="林七", entity_type="person", aliases=["七哥"], confidence="high"),
        ]
        result = v.validate(f, dictionary=dictionary)
        # character 名字修正
        assert any(c.name == "林七" for c in result.characters)
        # relationships 同步修正
        assert result.relationships[0].person_a == "林七"
        # events.actors 同步修正
        assert "林七" in result.events[0].actors

    def test_alias_chain_merge(self):
        """A.new_aliases 含 B 而 B 也作为独立 character 出现 → 合并。"""
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[
                CharacterFact(name="林七", new_aliases=["七哥"], abilities_gained=["御剑"]),
                CharacterFact(name="七哥", abilities_gained=["飞行"]),
            ],
        )
        result = v.validate(f, dictionary=[])
        # 七哥 被合并进林七
        names = {c.name for c in result.characters}
        assert "林七" in names
        assert "七哥" not in names
        # abilities 合并
        lin = next(c for c in result.characters if c.name == "林七")
        assert "御剑" in lin.abilities_gained
        assert "飞行" in lin.abilities_gained

    def test_relationship_filter_after_person_drop(self):
        """角色被过滤后，相关 relationship 也要清理。"""
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[CharacterFact(name="林七")],
            relationships=[
                RelationFact(person_a="林七", person_b="少年", relation_type="盟友"),  # 少年 被过滤
            ],
        )
        result = v.validate(f, dictionary=[])
        # "少年" 这个角色被过滤了，关系也没了
        assert len(result.relationships) == 0

    def test_event_actors_cleanup(self):
        """事件 actors 中已被过滤的角色应清空。"""
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[CharacterFact(name="林七")],
            events=[EventFact(event_type="other", title="对决", actors=["林七", "少年"])],
        )
        result = v.validate(f, dictionary=[])
        # "少年" 应被清掉
        assert result.events[0].actors == ["林七"]

    def test_validate_returns_new_object(self):
        """validate 应返回新对象，不修改原 fact。"""
        v = FactValidator()
        f = ChapterFact(
            chapter_number=1,
            characters=[CharacterFact(name="老者")],
        )
        result = v.validate(f, dictionary=[])
        # 原对象未被修改
        assert len(f.characters) == 1
        # 结果对象已过滤
        assert len(result.characters) == 0

    def test_is_generic_helpers(self):
        assert FactValidator.is_generic_person("少年")
        assert FactValidator.is_generic_person("林")  # 单字
        assert FactValidator.is_generic_person("")
        assert not FactValidator.is_generic_person("林七")

        assert FactValidator.is_generic_location("山")
        assert FactValidator.is_generic_location("门口")
        assert not FactValidator.is_generic_location("青云宗")


# ============================================================
# ChapterFactExtractor
# ============================================================


class TestChapterSplitting:
    def test_short_text_no_split(self):
        text = "短文本" * 100  # 300 字符
        segments = ChapterFactExtractor._split_long_chapter(text)
        assert len(segments) == 1

    def test_medium_text_two_split(self):
        # 构造 8000 字符（> SEGMENT_THRESHOLD_2=7000，<= SEGMENT_THRESHOLD_3=12000）
        line = "段落内容ABC\n"  # 8 字符
        text = line * (8000 // len(line) + 1)
        text = text[:8000]
        assert len(text) > ChapterFactExtractor.SEGMENT_THRESHOLD_2
        assert len(text) <= ChapterFactExtractor.SEGMENT_THRESHOLD_3
        segments = ChapterFactExtractor._split_long_chapter(text)
        assert len(segments) == 2
        assert "".join(segments) == text

    def test_long_text_three_split(self):
        # 构造 13000 字符（> SEGMENT_THRESHOLD_3=12000）
        line = "段落内容\n"  # 5 字符
        text = line * (13000 // len(line) + 1)
        text = text[:13000]
        assert len(text) > ChapterFactExtractor.SEGMENT_THRESHOLD_3
        segments = ChapterFactExtractor._split_long_chapter(text)
        assert len(segments) == 3
        assert "".join(segments) == text


class TestChapterExtraction:
    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": json.dumps({
            "summary": "主角林七初登场",
            "characters": [
                {"name": "林七", "role_hint": "protagonist",
                 "abilities_gained": ["御剑"], "evidence": "林七拔剑"}
            ],
            "relationships": [],
            "locations": [{"name": "青云宗", "type": "宗门"}],
            "events": [{"event_type": "join_org", "title": "拜入青云宗",
                        "importance": "high", "actors": ["林七"]}],
            "item_events": [],
            "org_events": [],
            "new_concepts": [],
        }, ensure_ascii=False)})
        extractor = ChapterFactExtractor(ai_service=ai)
        fact = await extractor.extract(
            chapter_number=1,
            chapter_title="第一章",
            chapter_text="林七拔剑。" * 50,
            dictionary=[],
        )
        assert fact.chapter_number == 1
        assert fact.summary == "主角林七初登场"
        assert len(fact.characters) == 1
        assert fact.characters[0].name == "林七"
        assert fact.characters[0].role_hint == "protagonist"
        assert len(fact.events) == 1
        assert fact.events[0].importance == "high"

    @pytest.mark.asyncio
    async def test_dictionary_injected_in_prompt(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": json.dumps({
            "summary": "...",
            "characters": [],
            "relationships": [],
            "locations": [],
            "events": [],
            "item_events": [],
            "org_events": [],
            "new_concepts": [],
        })})
        extractor = ChapterFactExtractor(ai_service=ai)
        dictionary = [
            DictionaryEntry(name="林七", entity_type="person", aliases=["七哥"], confidence="high"),
            DictionaryEntry(name="然后", entity_type="rejected", confidence="high"),
        ]
        await extractor.extract(
            chapter_number=1,
            chapter_title="t",
            chapter_text="正文",
            dictionary=dictionary,
        )
        prompt_arg = ai.generate_text.call_args.kwargs["prompt"]
        # 字典中 person 应出现在 prompt
        assert "林七" in prompt_arg
        # rejected 不应出现
        assert "然后" not in prompt_arg

    @pytest.mark.asyncio
    async def test_prior_summary_injected(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": "{}"})
        extractor = ChapterFactExtractor(ai_service=ai)
        await extractor.extract(
            chapter_number=2,
            chapter_title="t",
            chapter_text="正文",
            dictionary=[],
            prior_summary="前章摘要：林七拜入青云宗",
        )
        prompt_arg = ai.generate_text.call_args.kwargs["prompt"]
        assert "前章摘要：林七拜入青云宗" in prompt_arg

    @pytest.mark.asyncio
    async def test_llm_failure_raises_on_all_segments_empty(self):
        """所有段都返回空时抛 ChapterExtractionError。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock(side_effect=RuntimeError("LLM down"))
        extractor = ChapterFactExtractor(ai_service=ai)
        with pytest.raises(ChapterExtractionError):
            await extractor.extract(
                chapter_number=1,
                chapter_title="t",
                chapter_text="正文",
                dictionary=[],
            )

    @pytest.mark.asyncio
    async def test_invalid_json_recovers_with_empty_fact(self):
        """JSON 解析失败但调用成功 → 空 ChapterFact + 抛错（因为整段都没数据）。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": "not json"})
        extractor = ChapterFactExtractor(ai_service=ai)
        with pytest.raises(ChapterExtractionError):
            await extractor.extract(
                chapter_number=1,
                chapter_title="t",
                chapter_text="正文",
                dictionary=[],
            )

    @pytest.mark.asyncio
    async def test_partial_success_in_multi_segment(self):
        """多段抽取：一段成功一段失败，应只保留成功段。"""
        # "段落内容\n" = 5 字符；3000 行 = 15000 字符 > 12000 → 3 段切分
        long_text = "段落内容\n" * 3000
        responses = [
            json.dumps({"summary": "段1摘要",
                        "characters": [{"name": "林七"}],
                        "relationships": [], "locations": [],
                        "events": [], "item_events": [], "org_events": [],
                        "new_concepts": []}),
            "not json",  # 第 2 段失败
            json.dumps({"summary": "段3摘要",
                        "characters": [{"name": "慕容雪"}],
                        "relationships": [], "locations": [],
                        "events": [], "item_events": [], "org_events": [],
                        "new_concepts": []}),
        ]
        ai = MagicMock()
        ai.generate_text = AsyncMock(side_effect=[
            {"content": r} for r in responses
        ])
        extractor = ChapterFactExtractor(ai_service=ai)
        fact = await extractor.extract(
            chapter_number=1,
            chapter_title="t",
            chapter_text=long_text,
            dictionary=[],
        )
        names = {c.name for c in fact.characters}
        assert "林七" in names
        assert "慕容雪" in names

    @pytest.mark.asyncio
    async def test_skip_empty_text(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock()
        extractor = ChapterFactExtractor(ai_service=ai)
        fact = await extractor.extract(
            chapter_number=1,
            chapter_title="t",
            chapter_text="",
            dictionary=[],
        )
        assert fact.chapter_number == 1
        assert fact.characters == []
        ai.generate_text.assert_not_called()


class TestParseResponse:
    def test_invalid_event_importance_normalizes(self):
        ai = MagicMock()
        extractor = ChapterFactExtractor(ai_service=ai)
        raw = json.dumps({
            "summary": "...",
            "events": [{"event_type": "fight", "title": "战斗", "importance": "weird"}],
        })
        fact = extractor._parse_response(raw, 1, "t")
        assert fact.events[0].importance == "medium"

    def test_default_event_type(self):
        ai = MagicMock()
        extractor = ChapterFactExtractor(ai_service=ai)
        raw = json.dumps({"events": [{"title": "无类型事件"}]})
        fact = extractor._parse_response(raw, 1, "t")
        assert fact.events[0].event_type == "other"

    def test_skip_invalid_relationship(self):
        ai = MagicMock()
        extractor = ChapterFactExtractor(ai_service=ai)
        raw = json.dumps({
            "relationships": [
                {"person_a": "林七"},  # 缺 person_b 和 type，应跳过
                {"person_a": "林七", "person_b": "慕容雪", "relation_type": "盟友"},
            ]
        })
        fact = extractor._parse_response(raw, 1, "t")
        assert len(fact.relationships) == 1


class TestMergeSegments:
    def test_merge_characters(self):
        f1 = ChapterFact(chapter_number=1, characters=[
            CharacterFact(name="林七", abilities_gained=["御剑"]),
        ])
        f2 = ChapterFact(chapter_number=1, characters=[
            CharacterFact(name="林七", abilities_gained=["飞行"]),
            CharacterFact(name="慕容雪"),
        ])
        merged = ChapterFactExtractor._merge_segment_facts([f1, f2], 1, "t")
        names = {c.name for c in merged.characters}
        assert names == {"林七", "慕容雪"}
        lin = next(c for c in merged.characters if c.name == "林七")
        assert "御剑" in lin.abilities_gained
        assert "飞行" in lin.abilities_gained

    def test_merge_dedup_relationships(self):
        f1 = ChapterFact(chapter_number=1, relationships=[
            RelationFact(person_a="林七", person_b="慕容雪", relation_type="盟友"),
        ])
        f2 = ChapterFact(chapter_number=1, relationships=[
            RelationFact(person_a="林七", person_b="慕容雪", relation_type="盟友"),  # 重复
            RelationFact(person_a="林七", person_b="赵风", relation_type="敌对"),
        ])
        merged = ChapterFactExtractor._merge_segment_facts([f1, f2], 1, "t")
        assert len(merged.relationships) == 2

    def test_merge_dedup_events(self):
        f1 = ChapterFact(chapter_number=1, events=[
            EventFact(event_type="meet", title="初见"),
        ])
        f2 = ChapterFact(chapter_number=1, events=[
            EventFact(event_type="meet", title="初见"),  # 重复
            EventFact(event_type="fight", title="对决"),
        ])
        merged = ChapterFactExtractor._merge_segment_facts([f1, f2], 1, "t")
        titles = {e.title for e in merged.events}
        assert titles == {"初见", "对决"}
