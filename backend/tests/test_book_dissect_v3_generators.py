"""拆书 V3 R1 验收测试：5 个新 generator

覆盖：
- MethodologyGenerator
- StyleGenerator
- StructureGenerator
- ArchetypeGenerator
- WorldbuildingGenerator

测试维度：
- 正常 LLM 返回 → 字段清洗 + 结构正确
- LLM 抛异常 → 返回 None
- LLM 返回非 JSON → 返回 None
- 关键采样逻辑（topN / 章节窗口）
- prompt 中包含/排除特定内容
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.archetype_generator import ArchetypeGenerator
from app.services.book_dissect.event_timeline_builder import TimelineEvent
from app.services.book_dissect.methodology_generator import MethodologyGenerator
from app.services.book_dissect.structure_generator import StructureGenerator
from app.services.book_dissect.style_generator import StyleGenerator
from app.services.book_dissect.v2_types import (
    ChapterFact,
    EntityProfile,
    EventFact,
)
from app.services.book_dissect.synopsis_generator import SynopsisGenerator
from app.services.book_dissect.worldbuilding_generator import WorldbuildingGenerator


# ============================================================
# Mock AI helper
# ============================================================


def make_ai(content):
    """生成一个 mock AIService，返回指定内容（dict 自动 json.dumps）。"""
    ai = MagicMock()
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)
    ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


def make_failing_ai():
    ai = MagicMock()
    ai.generate_text = AsyncMock(side_effect=RuntimeError("LLM down"))
    return ai


# ============================================================
# 共享测试数据：人物 / 地点 / 事件
# ============================================================


def make_entities() -> list[EntityProfile]:
    return [
        EntityProfile(
            canonical_name="林七", entity_type="person", aliases=["七哥"],
            first_chapter=1, last_chapter=120, appearance_count=520,
            role_type="protagonist",
            profile_extras={"abilities": ["剑诀", "御火"]},
        ),
        EntityProfile(
            canonical_name="慕容雪", entity_type="person", aliases=["雪姐"],
            first_chapter=2, last_chapter=110, appearance_count=300,
            role_type="supporting",
        ),
        EntityProfile(
            canonical_name="楚天行", entity_type="person", aliases=[],
            first_chapter=10, last_chapter=80, appearance_count=80,
            role_type="antagonist",
        ),
        EntityProfile(
            canonical_name="青云宗", entity_type="location", aliases=[],
            first_chapter=1, last_chapter=80, appearance_count=200,
        ),
        EntityProfile(
            canonical_name="炼气境", entity_type="concept", aliases=[],
            first_chapter=1, last_chapter=120, appearance_count=50,
            profile_extras={"description": "修炼第一阶段"},
        ),
    ]


def make_timeline() -> list[TimelineEvent]:
    return [
        TimelineEvent(chapter_number=1, event_type="join_org", title="拜入青云宗",
                      actors=["林七"], importance="high"),
        TimelineEvent(chapter_number=20, event_type="fight", title="灭门之仇",
                      actors=["林七"], importance="high"),
        TimelineEvent(chapter_number=50, event_type="meet", title="日常对话",
                      actors=["林七"], importance="low"),
        TimelineEvent(chapter_number=100, event_type="breakthrough", title="突破金丹",
                      actors=["林七"], importance="high"),
    ]


def make_chapter_facts() -> list[ChapterFact]:
    return [
        ChapterFact(
            chapter_number=1, chapter_title="灭门之夜", summary="林七目睹家族被屠",
            events=[EventFact(event_type="fight", title="家族被灭", importance="high")],
        ),
        ChapterFact(
            chapter_number=2, chapter_title="逃亡", summary="林七孤身逃出",
            events=[EventFact(event_type="depart", title="逃出焚天谷", importance="medium")],
        ),
        ChapterFact(
            chapter_number=3, chapter_title="拜师", summary="拜入青云宗",
            events=[EventFact(event_type="join_org", title="拜入青云宗", importance="high")],
        ),
        ChapterFact(
            chapter_number=50, chapter_title="宗门大比", summary="参加宗门年度大比",
            events=[EventFact(event_type="fight", title="大比夺冠", importance="high")],
        ),
        ChapterFact(
            chapter_number=80, chapter_title="魔尊降临", summary="正派遭遇大敌",
            events=[EventFact(event_type="fight", title="对抗魔尊", importance="high")],
        ),
        ChapterFact(
            chapter_number=118, chapter_title="决战前夕", summary="终战之前",
            events=[EventFact(event_type="other", title="筹备", importance="medium")],
        ),
        ChapterFact(
            chapter_number=119, chapter_title="决战", summary="生死之战",
            events=[EventFact(event_type="fight", title="决战", importance="high")],
        ),
        ChapterFact(
            chapter_number=120, chapter_title="尾声", summary="尘埃落定",
            events=[EventFact(event_type="other", title="归隐", importance="low")],
        ),
    ]


def make_chapters_with_content():
    """构造伪 Chapter 对象（带 content / number / title 三个属性即可）。"""
    return [
        SimpleNamespace(number=i + 1, title=f"第{i+1}章", content="风轻轻吹过。" * 200)
        for i in range(8)
    ]


# ============================================================
# 1. MethodologyGenerator
# ============================================================


class TestMethodologyGenerator:

    @pytest.mark.asyncio
    async def test_basic_generate(self):
        ai = make_ai({
            "golden_finger_pattern": {
                "type": "传承流",
                "balance_mechanism": "传承需要主角实力达标才能解锁",
                "evolution_pattern": "随主角境界提升而解锁新功能",
                "writing_tips": "为自己的项目设计一个有解锁机制的金手指",
            },
            "opening_hook_pattern": {
                "hook_type": "灭门复仇流",
                "first_chapter_strategy": "首章直接展示灭门惨剧",
                "writing_tips": "用 100 字内的高密度冲突抓住读者",
            },
            "facepunch_rhythm": {
                "small_facepunch_freq": "每 3 章",
                "big_facepunch_freq": "每 30 章",
                "three_elements_pattern": "铺垫充分、反转干脆、震惊持久",
                "writing_tips": "提前埋伏笔为后期打脸服务",
            },
            "power_progression": {
                "system_type": "境界",
                "level_count": 9,
                "pace": "每 15 章一突破",
                "writing_tips": "境界数量不超过 12 个否则节奏太散",
            },
            "highlight_density": {
                "small_per_n_chapters": 3,
                "medium_per_n_chapters": 15,
                "big_per_n_chapters": 50,
                "writing_tips": "保持小爽点密度让读者持续追更",
            },
        })
        gen = MethodologyGenerator(ai_service=ai)
        result = await gen.generate(
            entities=make_entities(),
            timeline=make_timeline(),
            stats={"chapter_count": 120, "total_words": 600000, "chapters_extracted": 120},
        )
        assert result is not None
        assert result["golden_finger_pattern"]["type"] == "传承流"
        assert result["power_progression"]["level_count"] == 9
        assert result["highlight_density"]["small_per_n_chapters"] == 3

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        gen = MethodologyGenerator(ai_service=make_failing_ai())
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        gen = MethodologyGenerator(ai_service=make_ai("not json at all"))
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_only_high_importance_events_in_prompt(self):
        ai = make_ai("{}")
        gen = MethodologyGenerator(ai_service=ai)
        await gen.generate(
            entities=make_entities(), timeline=make_timeline(),
            stats={"chapter_count": 120},
        )
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        assert "拜入青云宗" in prompt        # high
        assert "灭门之仇" in prompt          # high
        assert "突破金丹" in prompt          # high
        assert "日常对话" not in prompt      # low 应被过滤

    @pytest.mark.asyncio
    async def test_missing_dim_filled_with_none(self):
        """LLM 只返回部分维度时，缺失维度应填 None 而非异常。"""
        ai = make_ai({
            "golden_finger_pattern": {"type": "系统流"},
            # 其余 4 个维度故意缺
        })
        gen = MethodologyGenerator(ai_service=ai)
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is not None
        assert result["golden_finger_pattern"]["type"] == "系统流"
        assert result["opening_hook_pattern"] is None
        assert result["facepunch_rhythm"] is None


# ============================================================
# 2. StyleGenerator
# ============================================================


class TestStyleGenerator:

    @pytest.mark.asyncio
    async def test_basic_generate(self):
        ai = make_ai({
            "name": "硬核冷静系",
            "description": "节奏快，句式短",
            "prompt_content": "你以冷静克制的笔法叙事，对话简短有力，动作描写细腻精准。",
            "traits": ["短句", "细描写", "冷叙事"],
        })
        gen = StyleGenerator(ai_service=ai)
        result = await gen.generate(make_chapters_with_content())
        assert result is not None
        assert result["name"] == "硬核冷静系"
        assert "冷静克制" in result["prompt_content"]
        assert "短句" in result["traits"]

    @pytest.mark.asyncio
    async def test_empty_chapters_returns_none(self):
        gen = StyleGenerator(ai_service=make_ai("{}"))
        assert await gen.generate([]) is None

    @pytest.mark.asyncio
    async def test_missing_prompt_content_returns_none(self):
        """V1 同款语义：prompt_content 缺失视为失败。"""
        ai = make_ai({"name": "X", "description": "Y"})
        gen = StyleGenerator(ai_service=ai)
        result = await gen.generate(make_chapters_with_content())
        assert result is None

    @pytest.mark.asyncio
    async def test_avoids_first_and_last_chapter(self):
        """5+ 章时应避开首末章。"""
        ai = make_ai("{}")
        gen = StyleGenerator(ai_service=ai)
        chapters = [
            SimpleNamespace(number=i + 1, title=f"第{i+1}章", content=f"标记{i+1}_" + ("内容" * 100))
            for i in range(8)
        ]
        await gen.generate(chapters)
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        assert "标记1_" not in prompt        # 首章被避开
        assert "标记8_" not in prompt        # 末章被避开

    @pytest.mark.asyncio
    async def test_few_chapters_uses_all(self):
        """章节较少时全用。"""
        ai = make_ai("{}")
        gen = StyleGenerator(ai_service=ai)
        chapters = [
            SimpleNamespace(number=i + 1, title=f"T{i}", content=f"标记{i+1}_" + ("文字" * 80))
            for i in range(2)
        ]
        await gen.generate(chapters)
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        # 2 章全用
        assert "标记1_" in prompt
        assert "标记2_" in prompt


# ============================================================
# 3. StructureGenerator
# ============================================================


class TestStructureGenerator:

    @pytest.mark.asyncio
    async def test_basic_generate(self):
        ai = make_ai({
            "opening_pattern": {
                "hook_subtype": "灭门复仇流",
                "tension_strategy": "首章灭门 → 次章逃亡 → 三章拜师，三步建立张力",
                "case": "第1章「灭门之夜」用直接惨剧开篇",
                "writing_tips": "用 3 章建立完整张力梯度",
            },
            "midpoint_conflict_escalation": {
                "boss_layer_pattern": "宗门内对手→敌对宗门→魔道中坚→魔尊",
                "escalation_pace": "每 30 章引入下一层",
                "case": "第50章宗门大比 / 第80章魔尊降临 形成两段升级",
                "writing_tips": "至少 4 层敌人形成楼梯型威胁递进",
            },
            "ending_hook_pattern": {
                "hook_subtypes": ["危机", "悬念"],
                "case": "第119章决战时切换 POV 留白",
                "writing_tips": "决战前一章用悬念钩子拉爆订阅",
            },
        })
        gen = StructureGenerator(ai_service=ai)
        result = await gen.generate(make_chapter_facts())
        assert result is not None
        assert result["opening_pattern"]["hook_subtype"] == "灭门复仇流"
        assert "危机" in result["ending_hook_pattern"]["hook_subtypes"]

    @pytest.mark.asyncio
    async def test_empty_facts_returns_none(self):
        gen = StructureGenerator(ai_service=make_ai("{}"))
        assert await gen.generate([]) is None

    @pytest.mark.asyncio
    async def test_opening_and_ending_in_prompt(self):
        ai = make_ai("{}")
        gen = StructureGenerator(ai_service=ai)
        await gen.generate(make_chapter_facts())
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        # 开篇 3 章
        assert "灭门之夜" in prompt
        assert "逃亡" in prompt
        # 末 3 章
        assert "决战前夕" in prompt
        assert "尾声" in prompt
        # 中段（high importance）
        assert "宗门大比" in prompt or "魔尊降临" in prompt

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        gen = StructureGenerator(ai_service=make_failing_ai())
        assert await gen.generate(make_chapter_facts()) is None


# ============================================================
# 4. ArchetypeGenerator
# ============================================================


class TestArchetypeGenerator:

    @pytest.mark.asyncio
    async def test_basic_generate(self):
        ai = make_ai({
            "protagonist_archetype": {
                "introduction_pattern": "首章惨剧推到主角面前",
                "characterization_pattern": "通过孤独 + 隐忍刻画主角内心",
                "growth_arc": "弱→强，内敛→爆发",
                "writing_tips": "为主角设计一个能持续刺激成长的钩子",
            },
            "supporting_archetype": {
                "introduction_pattern": "在主角需要帮助时登场",
                "function_in_story": "推进剧情 + 衬托主角",
                "case": "第2章慕容雪救主角",
                "writing_tips": "每个配角都要有独立的功能价值",
            },
            "antagonist_archetype": {
                "escalation_pattern": "门派对手 → 魔道高手 → 魔尊",
                "characterization_strategy": "给反派一个可被理解的动机",
                "writing_tips": "避免脸谱化，反派也要有目标和原则",
            },
        })
        gen = ArchetypeGenerator(ai_service=ai)
        relations = [
            SimpleNamespace(person_a="林七", person_b="慕容雪", category="intimate", count=50),
            SimpleNamespace(person_a="林七", person_b="楚天行", category="hostile", count=30),
        ]
        result = await gen.generate(make_entities(), relations)
        assert result is not None
        assert "孤独" in result["protagonist_archetype"]["characterization_pattern"]
        assert result["antagonist_archetype"]["escalation_pattern"]

    @pytest.mark.asyncio
    async def test_no_persons_returns_none(self):
        gen = ArchetypeGenerator(ai_service=make_ai("{}"))
        # 没有任何 person 实体
        result = await gen.generate(
            entities=[
                EntityProfile(canonical_name="X", entity_type="location",
                              first_chapter=1, last_chapter=10, appearance_count=5),
            ],
            relations=[],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_relations_top_n_in_prompt(self):
        ai = make_ai("{}")
        gen = ArchetypeGenerator(ai_service=ai)
        gen.TOP_RELATIONS = 1
        relations = [
            SimpleNamespace(person_a="A", person_b="B", category="family", count=5),
            SimpleNamespace(person_a="C", person_b="D", category="family", count=100),
        ]
        await gen.generate(make_entities(), relations)
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        # count 高的 C-D 入选；A-B 被截断
        assert "C ↔ D" in prompt
        assert "A ↔ B" not in prompt

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        gen = ArchetypeGenerator(ai_service=make_failing_ai())
        assert await gen.generate(make_entities(), []) is None


# ============================================================
# 5. WorldbuildingGenerator
# ============================================================


class TestWorldbuildingGenerator:

    @pytest.mark.asyncio
    async def test_basic_generate(self):
        ai = make_ai({
            "era_design": {
                "anchor_type": "修真大陆",
                "case": "青云大陆，分九大宗门",
                "writing_tips": "时代锚点决定整个世界的氛围基调",
            },
            "location_hierarchy_design": {
                "depth": 3,
                "chain_example": "大陆→宗门→殿堂",
                "case": "青云宗内三层殿堂结构",
                "writing_tips": "层级深度 3-4 层最易让读者建立空间感",
            },
            "rule_balance_design": {
                "core_rules_summary": "境界压制 + 道法属性相克",
                "balance_mechanism": "高境界压低境界，但属性相克可以越级战斗",
                "writing_tips": "规则要既给主角希望，又给反派威胁",
            },
        })
        gen = WorldbuildingGenerator(ai_service=ai)
        parent_map = {"青云宗": None}
        result = await gen.generate(make_entities(), parent_map=parent_map)
        assert result is not None
        assert result["era_design"]["anchor_type"] == "修真大陆"
        assert result["location_hierarchy_design"]["depth"] == 3

    @pytest.mark.asyncio
    async def test_no_locations_orgs_concepts_returns_none(self):
        gen = WorldbuildingGenerator(ai_service=make_ai("{}"))
        # 只剩人物
        result = await gen.generate(
            entities=[
                EntityProfile(canonical_name="X", entity_type="person",
                              first_chapter=1, last_chapter=10, appearance_count=5),
            ],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_concepts_in_rule_clues(self):
        ai = make_ai("{}")
        gen = WorldbuildingGenerator(ai_service=ai)
        await gen.generate(make_entities())
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        # 概念字段出现在 rule_clues
        assert "炼气境" in prompt
        assert "修炼第一阶段" in prompt

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        gen = WorldbuildingGenerator(ai_service=make_failing_ai())
        assert await gen.generate(make_entities()) is None


# ============================================================
# V3.2 SynopsisGenerator 测试（synopsis 复活）
#
# 验收要点：
# 1. 正常返回：8 字段全输出，sanitize 正确
# 2. selling_points 始终是字符串列表（即使 LLM 返回字符串/单值）
# 3. LLM 失败/非 JSON → 返回 None
# 4. **匿名化**：prompt 不含具体人名（防 LLM 复刻原书）
# ============================================================


class TestSynopsisGenerator:

    @pytest.mark.asyncio
    async def test_basic_generate(self):
        ai = make_ai({
            "genre_tag": "仙侠",
            "core_premise": "少年主角因家族变故踏入修行路，逐渐揭开身世之谜并争夺最高境界。",
            "golden_finger_concept": "传承流：开局获得已陨落强者的境界传承",
            "power_system_overview": "境界等级（炼气-筑基-金丹-元婴）+ 五行属性相克",
            "central_conflict": "复仇 + 争霸",
            "ultimate_goal": "成神成圣",
            "selling_points": ["爽文", "打脸", "装逼", "热血"],
            "target_audience_signals": "男频热血型",
        })
        gen = SynopsisGenerator(ai_service=ai)
        result = await gen.generate(
            entities=make_entities(),
            timeline=make_timeline(),
            stats={"chapter_count": 120, "total_words": 600000, "chapters_extracted": 120},
        )
        assert result is not None
        assert result["genre_tag"] == "仙侠"
        assert "境界" in result["power_system_overview"]
        assert isinstance(result["selling_points"], list)
        assert len(result["selling_points"]) == 4
        assert "爽文" in result["selling_points"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        gen = SynopsisGenerator(ai_service=make_failing_ai())
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        gen = SynopsisGenerator(ai_service=make_ai("not json"))
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_selling_points_non_list_becomes_empty(self):
        """LLM 返回 selling_points 为字符串而非列表时，sanitize 应把它清成 []。"""
        ai = make_ai({
            "genre_tag": "玄幻",
            "selling_points": "爽文、打脸、装逼",  # 字符串而非列表
        })
        gen = SynopsisGenerator(ai_service=ai)
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is not None
        # selling_points 应被强制规范成 list（这里非 list 输入会变 []）
        assert isinstance(result["selling_points"], list)
        assert result["selling_points"] == []

    @pytest.mark.asyncio
    async def test_prompt_anonymizes_character_names(self):
        """V3.2 关键：prompt 中不能直接出现具体人名（防 LLM 复刻原书）。"""
        ai = make_ai("{}")
        gen = SynopsisGenerator(ai_service=ai)
        await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={"chapter_count": 120},
        )
        prompt = ai.generate_text.call_args.kwargs["prompt"]
        # make_entities 里的具体姓名不该出现在 prompt 中
        assert "林七" not in prompt
        assert "慕容雪" not in prompt
        assert "楚天行" not in prompt
        # 但角色配置类型（protagonist 等）应该出现
        assert "protagonist" in prompt or "主角" in prompt or "型角色" in prompt

    @pytest.mark.asyncio
    async def test_sanitize_handles_partial_dict(self):
        """LLM 只返回部分字段时，缺失字段填 None / 空列表。"""
        ai = make_ai({
            "genre_tag": "都市",
            # 其他字段省略
        })
        gen = SynopsisGenerator(ai_service=ai)
        result = await gen.generate(
            entities=make_entities(), timeline=make_timeline(), stats={},
        )
        assert result is not None
        assert result["genre_tag"] == "都市"
        # 缺失的 8 字段应有占位
        assert "core_premise" in result
        assert "selling_points" in result
        assert result["selling_points"] == []  # list 缺失走 []
        assert result["core_premise"] is None  # 标量缺失走 None
