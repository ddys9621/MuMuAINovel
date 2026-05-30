"""拆书 V2 Phase 5 验收测试

覆盖：
- AliasResolver: Union-Find 别名归一 + 不安全词过滤
- EntityAggregator: 全书角色 / 地点档案聚合
- RelationAggregator: 关系归一 + 跨章合并
- LocationHierarchyBuilder: 地点层级 + 环检测
- EventTimelineBuilder: 事件时间线
"""

from app.services.book_dissect.alias_resolver import AliasResolver
from app.services.book_dissect.entity_aggregator import EntityAggregator
from app.services.book_dissect.event_timeline_builder import EventTimelineBuilder
from app.services.book_dissect.location_hierarchy import LocationHierarchyBuilder
from app.services.book_dissect.relation_aggregator import (
    RelationAggregator,
    normalize_relation_category,
)
from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    DictionaryEntry,
    EntityProfile,
    EntityType,
    EventFact,
    Importance,
    LocationFact,
    RelationCategory,
    RelationFact,
)


# ============================================================
# AliasResolver
# ============================================================


class TestAliasResolver:
    def test_dictionary_alias_groups(self):
        r = AliasResolver()
        dictionary = [
            DictionaryEntry(
                name="林七", entity_type="person",
                aliases=["七哥", "林少"], confidence="high", frequency=42,
            ),
            DictionaryEntry(
                name="慕容雪", entity_type="person",
                aliases=[], confidence="high", frequency=30,
            ),
        ]
        result = r.resolve(dictionary, [])
        assert result["林七"] == "林七"
        assert result["七哥"] == "林七"
        assert result["林少"] == "林七"
        assert result["慕容雪"] == "慕容雪"

    def test_chapter_facts_alias_merge(self):
        r = AliasResolver()
        facts = [
            ChapterFact(
                chapter_number=1,
                characters=[
                    CharacterFact(name="林七", new_aliases=["七哥"]),
                ],
            ),
            ChapterFact(
                chapter_number=2,
                characters=[
                    CharacterFact(name="林七", new_aliases=["林少"]),
                ],
            ),
        ]
        result = r.resolve([], facts)
        # 林七 是 canonical（频率最高）
        assert result["林七"] == "林七"
        assert result["七哥"] == "林七"
        assert result["林少"] == "林七"

    def test_unsafe_alias_excluded(self):
        """'师父' 是不安全词，不应作为 UF 节点合并。"""
        r = AliasResolver()
        facts = [
            ChapterFact(
                chapter_number=1,
                characters=[
                    CharacterFact(name="林七", new_aliases=["师父"]),
                ],
            ),
            ChapterFact(
                chapter_number=2,
                characters=[
                    CharacterFact(name="慕容雪", new_aliases=["师父"]),
                ],
            ),
        ]
        result = r.resolve([], facts)
        # "师父" 不应作为 alias 出现在 result 中
        # （因为它是 unsafe，不参与 UF）
        assert "师父" not in result
        # 林七 / 慕容雪 各自独立
        assert result["林七"] == "林七"
        assert result["慕容雪"] == "慕容雪"

    def test_canonical_selection_short_name_preferred(self):
        r = AliasResolver()
        # 频率相同时短的优先
        dictionary = [
            DictionaryEntry(
                name="天才少年林七", entity_type="person",
                aliases=["林七"], confidence="medium", frequency=10,
            ),
        ]
        result = r.resolve(dictionary, [])
        # 频率：天才少年林七=10，林七=1（来自 alias 累加）
        # 频率不同，"天才少年林七"频率更高 → canonical
        assert result["天才少年林七"] == "天才少年林七"

    def test_canonical_select_when_freq_tied(self):
        r = AliasResolver()
        # 构造频率相同的两个候选
        members = ["aaaaa", "bb", "ccc"]
        freq = {"aaaaa": 5, "bb": 5, "ccc": 5}
        canon = AliasResolver._select_canonical(members, freq)
        # 短的优先
        assert canon == "bb"

    def test_is_unsafe_alias(self):
        assert AliasResolver.is_unsafe_alias("师父")
        assert AliasResolver.is_unsafe_alias("哥")
        assert AliasResolver.is_unsafe_alias("那人")
        assert AliasResolver.is_unsafe_alias("")
        assert not AliasResolver.is_unsafe_alias("林七")


# ============================================================
# EntityAggregator
# ============================================================


class TestEntityAggregator:
    def test_aggregate_basic_persons(self):
        agg = EntityAggregator()
        facts = [
            ChapterFact(
                chapter_number=1,
                characters=[
                    CharacterFact(
                        name="林七", role_hint="protagonist",
                        abilities_gained=["御剑"],
                        appearance="青衣少年",
                    ),
                ],
            ),
            ChapterFact(
                chapter_number=3,
                characters=[
                    CharacterFact(
                        name="林七", role_hint="protagonist",
                        abilities_gained=["御火"],
                        new_aliases=["七哥"],
                    ),
                ],
            ),
            ChapterFact(
                chapter_number=5,
                characters=[
                    CharacterFact(name="七哥", role_hint="protagonist"),
                ],
            ),
        ]
        alias_map = {"七哥": "林七", "林七": "林七"}
        dictionary = [
            DictionaryEntry(name="林七", entity_type="person", aliases=["七哥"], confidence="high"),
        ]
        result = agg.aggregate(facts, alias_map, dictionary)

        # 应该只有一个聚合实体
        assert len(result) == 1
        lin = result[0]
        assert lin.canonical_name == "林七"
        assert lin.entity_type == "person"
        assert lin.appearance_count == 3
        assert lin.first_chapter == 1
        assert lin.last_chapter == 5
        assert lin.role_type == "protagonist"
        assert "七哥" in lin.aliases
        assert "御剑" in lin.profile_extras["abilities"]
        assert "御火" in lin.profile_extras["abilities"]
        assert lin.profile_extras["appearance"] == "青衣少年"

    def test_role_type_voting(self):
        """role_hint 投票：3 票 supporting + 1 票 protagonist → 投票阶段 supporting。

        V4.2.3 后续：因为这场景只有 1 个 person 且无 protagonist，
        F4 兜底会把它升级为 protagonist，原投票结果存入 _role_type_original。
        本测试同时验证投票算法 + 兜底升级的联动。
        """
        agg = EntityAggregator()
        facts = []
        for ch in (1, 2, 3):
            facts.append(ChapterFact(
                chapter_number=ch,
                characters=[CharacterFact(name="陆天", role_hint="supporting")],
            ))
        facts.append(ChapterFact(
            chapter_number=4,
            characters=[CharacterFact(name="陆天", role_hint="protagonist")],
        ))
        result = agg.aggregate(facts, {"陆天": "陆天"}, [])
        lu = next(p for p in result if p.canonical_name == "陆天")
        # 兜底后 role_type = protagonist（场景里没有别的 protagonist 候选）
        assert lu.role_type == "protagonist"
        # 但兜底标记保留：投票原始结果 = supporting
        assert lu.profile_extras.get("_role_type_fallback") is True
        assert lu.profile_extras.get("_role_type_original") == "supporting"

    def test_role_type_voting_no_fallback_when_protagonist_exists(self):
        """V4.2.3 新增：当场景中已有 protagonist 时，投票结果不被兜底覆盖。

        2 个 person：'陆天' 投 3 supporting 1 protagonist → 投票 supporting
        '林七' 投 1 protagonist → 投票 protagonist
        因为已有 protagonist，'陆天' 不会被兜底升级。
        """
        agg = EntityAggregator()
        facts = []
        for ch in (1, 2, 3):
            facts.append(ChapterFact(
                chapter_number=ch,
                characters=[CharacterFact(name="陆天", role_hint="supporting")],
            ))
        facts.append(ChapterFact(
            chapter_number=4,
            characters=[
                CharacterFact(name="陆天", role_hint="protagonist"),
                CharacterFact(name="林七", role_hint="protagonist"),
            ],
        ))
        result = agg.aggregate(facts, {"陆天": "陆天", "林七": "林七"}, [])
        lu_lt = next(p for p in result if p.canonical_name == "陆天")
        lu_lq = next(p for p in result if p.canonical_name == "林七")
        # '陆天' 投票 supporting 胜出 → 不被兜底
        assert lu_lt.role_type == "supporting"
        assert "_role_type_fallback" not in lu_lt.profile_extras
        # '林七' 投票 protagonist
        assert lu_lq.role_type == "protagonist"

    def test_aggregate_locations(self):
        agg = EntityAggregator()
        facts = [
            ChapterFact(chapter_number=1, locations=[
                LocationFact(name="青云宗", type="宗门", description="千年门派"),
            ]),
            ChapterFact(chapter_number=2, locations=[
                LocationFact(name="青云宗", parent="苍云大陆"),
            ]),
        ]
        dictionary = [DictionaryEntry(name="青云宗", entity_type="location", confidence="high")]
        result = agg.aggregate(facts, {}, dictionary)
        loc = next(p for p in result if p.canonical_name == "青云宗")
        assert loc.appearance_count == 2
        assert loc.profile_extras["type"] == "宗门"
        assert loc.profile_extras["description"] == "千年门派"
        assert loc.profile_extras["parent"] == "苍云大陆"

    def test_sort_order(self):
        """person 应排在 location 前面。"""
        agg = EntityAggregator()
        facts = [
            ChapterFact(chapter_number=1,
                characters=[CharacterFact(name="林七")],
                locations=[LocationFact(name="青云宗")]),
        ]
        dictionary = [
            DictionaryEntry(name="林七", entity_type="person", confidence="high"),
            DictionaryEntry(name="青云宗", entity_type="location", confidence="high"),
        ]
        result = agg.aggregate(facts, {}, dictionary)
        # person 优先
        assert result[0].entity_type == "person"
        assert result[1].entity_type == "location"


# ============================================================
# RelationAggregator
# ============================================================


class TestNormalizeRelationCategory:
    def test_family(self):
        assert normalize_relation_category("父子") == "family"
        assert normalize_relation_category("亲兄弟") == "family"

    def test_intimate(self):
        assert normalize_relation_category("夫妻") == "intimate"
        assert normalize_relation_category("情侣") == "intimate"

    def test_hierarchical(self):
        assert normalize_relation_category("师徒") == "hierarchical"
        assert normalize_relation_category("师父") == "hierarchical"
        assert normalize_relation_category("上下级") == "hierarchical"

    def test_social(self):
        assert normalize_relation_category("好友") == "social"
        assert normalize_relation_category("结义兄弟") == "family"  # "兄弟" 比"结义" 优先匹配

    def test_hostile(self):
        assert normalize_relation_category("敌对") == "hostile"
        assert normalize_relation_category("仇人") == "hostile"

    def test_other(self):
        assert normalize_relation_category("莫名关系") == "other"
        assert normalize_relation_category("") == "other"


class TestRelationAggregator:
    def test_basic_aggregate(self):
        a = RelationAggregator()
        facts = [
            ChapterFact(chapter_number=1, relationships=[
                RelationFact(person_a="林七", person_b="慕容雪", relation_type="师徒",
                             evidence="林七拜师"),
            ]),
            ChapterFact(chapter_number=3, relationships=[
                RelationFact(person_a="林七", person_b="慕容雪", relation_type="师徒",
                             evidence="师徒互动"),
            ]),
        ]
        entities = [
            EntityProfile(canonical_name="林七", entity_type="person"),
            EntityProfile(canonical_name="慕容雪", entity_type="person"),
        ]
        result = a.aggregate(facts, alias_map={}, entities=entities)
        assert len(result) == 1
        rel = result[0]
        assert rel.entity_a == "林七"
        assert rel.entity_b == "慕容雪"
        assert rel.relation_category == "hierarchical"
        assert rel.occurrence_count == 2
        assert rel.first_chapter == 1
        assert len(rel.evidence) == 2

    def test_skip_unknown_endpoints(self):
        """端点不在 entities 中 → 丢弃。"""
        a = RelationAggregator()
        facts = [ChapterFact(chapter_number=1, relationships=[
            RelationFact(person_a="林七", person_b="路人甲", relation_type="盟友"),
        ])]
        entities = [EntityProfile(canonical_name="林七", entity_type="person")]
        result = a.aggregate(facts, alias_map={}, entities=entities)
        assert result == []

    def test_alias_normalization(self):
        a = RelationAggregator()
        facts = [ChapterFact(chapter_number=1, relationships=[
            RelationFact(person_a="七哥", person_b="慕容雪", relation_type="盟友"),
        ])]
        entities = [
            EntityProfile(canonical_name="林七", entity_type="person"),
            EntityProfile(canonical_name="慕容雪", entity_type="person"),
        ]
        alias_map = {"七哥": "林七"}
        result = a.aggregate(facts, alias_map=alias_map, entities=entities)
        assert result[0].entity_a == "林七"

    def test_self_loop_dropped(self):
        a = RelationAggregator()
        facts = [ChapterFact(chapter_number=1, relationships=[
            RelationFact(person_a="林七", person_b="林七", relation_type="盟友"),
        ])]
        entities = [EntityProfile(canonical_name="林七", entity_type="person")]
        result = a.aggregate(facts, alias_map={}, entities=entities)
        assert result == []


# ============================================================
# LocationHierarchyBuilder
# ============================================================


class TestLocationHierarchy:
    def test_basic_hierarchy(self):
        b = LocationHierarchyBuilder()
        facts = [ChapterFact(chapter_number=1, locations=[
            LocationFact(name="青云宗", parent="苍云大陆"),
            LocationFact(name="苍云大陆"),
        ])]
        entities = [
            EntityProfile(canonical_name="青云宗", entity_type="location"),
            EntityProfile(canonical_name="苍云大陆", entity_type="location"),
        ]
        result = b.build(facts, alias_map={}, entities=entities)
        assert result["青云宗"] == "苍云大陆"
        assert result["苍云大陆"] is None

    def test_voting(self):
        """同一地点多次出现，多数 parent 投票胜出。"""
        b = LocationHierarchyBuilder()
        facts = [
            ChapterFact(chapter_number=1, locations=[LocationFact(name="A", parent="B")]),
            ChapterFact(chapter_number=2, locations=[LocationFact(name="A", parent="B")]),
            ChapterFact(chapter_number=3, locations=[LocationFact(name="A", parent="C")]),
        ]
        entities = [
            EntityProfile(canonical_name="A", entity_type="location"),
            EntityProfile(canonical_name="B", entity_type="location"),
            EntityProfile(canonical_name="C", entity_type="location"),
        ]
        result = b.build(facts, alias_map={}, entities=entities)
        assert result["A"] == "B"  # 票数 2 > 1

    def test_cycle_break(self):
        """A.parent=B + B.parent=A → 弱边被打破。"""
        b = LocationHierarchyBuilder()
        facts = [
            # A.parent=B 出现 3 次（更多）
            ChapterFact(chapter_number=1, locations=[LocationFact(name="A", parent="B")]),
            ChapterFact(chapter_number=2, locations=[LocationFact(name="A", parent="B")]),
            ChapterFact(chapter_number=3, locations=[LocationFact(name="A", parent="B")]),
            # B.parent=A 出现 1 次（弱）
            ChapterFact(chapter_number=4, locations=[LocationFact(name="B", parent="A")]),
        ]
        entities = [
            EntityProfile(canonical_name="A", entity_type="location"),
            EntityProfile(canonical_name="B", entity_type="location"),
        ]
        result = b.build(facts, alias_map={}, entities=entities)
        # A→B 应保留，B→A 弱边被打破
        assert result["A"] == "B"
        assert result["B"] is None

    def test_no_parent_to_none(self):
        b = LocationHierarchyBuilder()
        facts = [ChapterFact(chapter_number=1, locations=[LocationFact(name="孤岛")])]
        entities = [EntityProfile(canonical_name="孤岛", entity_type="location")]
        result = b.build(facts, alias_map={}, entities=entities)
        assert result["孤岛"] is None


# ============================================================
# EventTimelineBuilder
# ============================================================


class TestEventTimelineBuilder:
    def test_basic(self):
        b = EventTimelineBuilder()
        facts = [
            ChapterFact(chapter_number=2, events=[
                EventFact(event_type="meet", title="再遇", actors=["林七"], importance="medium"),
            ]),
            ChapterFact(chapter_number=1, events=[
                EventFact(event_type="meet", title="初遇师父", actors=["林七"], importance="high"),
                EventFact(event_type="other", title="背景", importance="low"),
            ]),
        ]
        result = b.build(facts, alias_map={})
        # 按章节序排列
        assert result[0].chapter_number == 1
        assert result[1].chapter_number == 1
        assert result[2].chapter_number == 2
        # 同章节按 importance 排（high 先）
        assert result[0].title == "初遇师父"
        assert result[1].title == "背景"

    def test_alias_normalize_actors(self):
        b = EventTimelineBuilder()
        facts = [ChapterFact(chapter_number=1, events=[
            EventFact(event_type="meet", title="ev", actors=["七哥"]),
        ])]
        result = b.build(facts, alias_map={"七哥": "林七"})
        assert result[0].actors == ["林七"]
