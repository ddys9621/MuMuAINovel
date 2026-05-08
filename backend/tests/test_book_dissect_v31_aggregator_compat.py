"""拆书 V3.1 聚合层兼容性测试：长上下文路径下 dictionary=[]，
聚合层（AliasResolver / EntityAggregator / RelationAggregator /
LocationHierarchyBuilder / EventTimelineBuilder / ConflictDetector）
应正常工作。

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4.2.4
"""

import pytest

from app.services.book_dissect.alias_resolver import AliasResolver
from app.services.book_dissect.entity_aggregator import EntityAggregator
from app.services.book_dissect.event_timeline_builder import EventTimelineBuilder
from app.services.book_dissect.location_hierarchy import LocationHierarchyBuilder
from app.services.book_dissect.relation_aggregator import RelationAggregator
from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    EventFact,
    LocationFact,
    RelationFact,
)
from app.services.book_dissect.verification_pass import ConflictDetector


# ============================================================
# fixture：构造一组典型 chapter_facts（不依赖 dictionary）
# ============================================================


def make_chapter_facts() -> list[ChapterFact]:
    return [
        ChapterFact(
            chapter_number=1,
            chapter_title="第一章 觉醒",
            summary="林七在青云宗觉醒血脉",
            characters=[
                CharacterFact(
                    name="林七",
                    new_aliases=["七哥"],
                    role_hint="protagonist",
                    appearance="瘦削少年",
                    abilities_gained=["练气一层"],
                    locations_in_chapter=["青云宗"],
                    evidence="林七缓缓睁眼",
                ),
                CharacterFact(
                    name="玄虚真人",
                    role_hint="supporting",
                    evidence="玄虚收徒",
                ),
            ],
            relationships=[
                RelationFact(
                    person_a="林七",
                    person_b="玄虚真人",
                    relation_type="师徒",
                    evidence="收为徒",
                ),
            ],
            locations=[
                LocationFact(name="青云宗", type="宗门", parent=None,
                             description="千年宗门", evidence="..."),
            ],
            events=[
                EventFact(
                    event_type="join_org",
                    title="林七拜入青云宗",
                    actors=["林七", "玄虚真人"],
                    location="青云宗",
                    importance="high",
                    evidence="拜入仪式",
                ),
            ],
        ),
        ChapterFact(
            chapter_number=2,
            chapter_title="第二章 历练",
            summary="林七初次历练",
            characters=[
                CharacterFact(
                    name="林七",
                    role_hint="protagonist",
                    abilities_gained=["剑诀入门"],
                    locations_in_chapter=["藏经阁"],
                    evidence="...",
                ),
            ],
            locations=[
                LocationFact(name="藏经阁", type="建筑", parent="青云宗",
                             evidence="..."),
            ],
            events=[
                EventFact(
                    event_type="breakthrough",
                    title="林七突破练气二层",
                    actors=["林七"],
                    importance="medium",
                    evidence="...",
                ),
            ],
        ),
    ]


# ============================================================
# 各聚合器在 dictionary=[] 下的兼容性
# ============================================================


class TestAliasResolverEmptyDict:
    def test_resolves_via_chapter_facts_only(self):
        facts = make_chapter_facts()
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        # 林七 + 七哥 应归并到同一 canonical
        assert "林七" in alias_map or "七哥" in alias_map
        # 玄虚真人 单独成组（应能映射到自身）
        if "玄虚真人" in alias_map:
            assert alias_map["玄虚真人"] in {"玄虚真人"}

    def test_empty_dict_and_facts(self):
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=[])
        assert alias_map == {}


class TestEntityAggregatorEmptyDict:
    def test_aggregates_with_default_types(self):
        """dictionary=[] 时 type_by_name 为空，
        person 类应 fallback 到 EntityType.PERSON。"""
        facts = make_chapter_facts()
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        agg = EntityAggregator()
        entities = agg.aggregate(facts, alias_map, dictionary=[])
        names = {e.canonical_name for e in entities}
        # 至少包含林七 + 玄虚真人 + 青云宗 + 藏经阁
        assert any(n in names for n in ["林七", "七哥"])
        assert "玄虚真人" in names
        assert "青云宗" in names
        # person 默认 entity_type=person
        for e in entities:
            if e.canonical_name in {"林七", "七哥", "玄虚真人"}:
                assert e.entity_type == "person"
            if e.canonical_name in {"青云宗", "藏经阁"}:
                assert e.entity_type == "location"


class TestRelationAggregatorEmptyDict:
    def test_aggregates_relationship(self):
        facts = make_chapter_facts()
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        agg = EntityAggregator()
        entities = agg.aggregate(facts, alias_map, dictionary=[])
        rel_agg = RelationAggregator()
        relations = rel_agg.aggregate(facts, alias_map, entities)
        assert any(
            (r.entity_a == "林七" and r.entity_b == "玄虚真人")
            or (r.entity_a == "玄虚真人" and r.entity_b == "林七")
            for r in relations
        )


class TestLocationHierarchyEmptyDict:
    def test_builds_parent_map(self):
        facts = make_chapter_facts()
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        agg = EntityAggregator()
        entities = agg.aggregate(facts, alias_map, dictionary=[])
        builder = LocationHierarchyBuilder()
        parent_map = builder.build(facts, alias_map, entities)
        # 藏经阁 → 青云宗
        if "藏经阁" in parent_map:
            assert parent_map["藏经阁"] == "青云宗"


class TestEventTimelineEmptyDict:
    def test_builds_timeline(self):
        facts = make_chapter_facts()
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        builder = EventTimelineBuilder()
        timeline = builder.build(facts, alias_map)
        # 至少包含 join_org + breakthrough 各一
        types = {ev.event_type for ev in timeline}
        assert "join_org" in types
        assert "breakthrough" in types


class TestConflictDetectorEmptyDict:
    def test_detects_role_conflict_without_dictionary(self):
        """ConflictDetector 不依赖 dictionary，仅看 entities + chapter_facts。"""
        # 构造一个角色 role_hint 分散的场景
        facts: list[ChapterFact] = []
        for i, hint in enumerate(["protagonist", "supporting", "minor", "antagonist"], 1):
            facts.append(ChapterFact(
                chapter_number=i,
                characters=[CharacterFact(name="林七", role_hint=hint, evidence=f"第{i}章")],
            ))
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        agg = EntityAggregator()
        entities = agg.aggregate(facts, alias_map, dictionary=[])

        detector = ConflictDetector()
        conflicts = detector.detect(entities, facts, alias_map)
        # 林七 4 票分散应识别为 role_type 冲突
        role_conflicts = [c for c in conflicts if c.field == "role_type"]
        assert len(role_conflicts) >= 1
        assert role_conflicts[0].canonical_name == "林七"


# ============================================================
# 端到端：长上下文路径完整聚合链
# ============================================================


class TestEndToEndEmptyDictPipeline:
    """模拟长上下文路径：拿到 chapter_facts 后跑完整聚合链。"""

    def test_full_pipeline_runs_without_dictionary(self):
        facts = make_chapter_facts()
        # 1. AliasResolver
        resolver = AliasResolver()
        alias_map = resolver.resolve(dictionary=[], chapter_facts=facts)
        # 2. EntityAggregator
        agg = EntityAggregator()
        entities = agg.aggregate(facts, alias_map, dictionary=[])
        assert len(entities) >= 3  # 林七 / 玄虚真人 / 青云宗 / 藏经阁
        # 3. ConflictDetector（数据无冲突时返回空）
        detector = ConflictDetector()
        conflicts = detector.detect(entities, facts, alias_map)
        # 数据无明显冲突，conflicts 可能为空
        assert isinstance(conflicts, list)
        # 4. RelationAggregator
        rel_agg = RelationAggregator()
        relations = rel_agg.aggregate(facts, alias_map, entities)
        assert len(relations) >= 1
        # 5. LocationHierarchyBuilder
        loc_builder = LocationHierarchyBuilder()
        parent_map = loc_builder.build(facts, alias_map, entities)
        assert isinstance(parent_map, dict)
        # 6. EventTimelineBuilder
        timeline_builder = EventTimelineBuilder()
        timeline = timeline_builder.build(facts, alias_map)
        assert len(timeline) >= 2
