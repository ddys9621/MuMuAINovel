"""V3.2-P2：拆书参考包模式三维度聚合 generator 单测。

覆盖：
- EntitiesPatternGenerator：类型分布、命名风格信号、空数据
- RelationsPatternGenerator：类别分布、top 类型、空数据
- EventsPatternGenerator：类型/重要性分布、密度、空数据
- build_pattern_dimensions：3 个一站式输出 + 异常容错
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.pattern_generators import (
    EntitiesPatternGenerator,
    EventsPatternGenerator,
    RelationsPatternGenerator,
    _name_style_signals,
    _safe_count_dict,
    build_pattern_dimensions,
)


# ============================================================
# 公共构造工具
# ============================================================

def make_db_with_rows(rows):
    """构造一个 AsyncSession-like mock，db.execute(...).scalars().all() 返回 rows。"""
    db = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    db.execute = AsyncMock(return_value=result)
    return db


def make_entity(*, name, entity_type="person", role_type=None):
    return SimpleNamespace(
        canonical_name=name,
        entity_type=entity_type,
        role_type=role_type,
    )


def make_relation(*, category, relation_type, occurrence=1):
    return SimpleNamespace(
        relation_category=category,
        relation_type=relation_type,
        occurrence_count=occurrence,
    )


def make_event(*, event_type, importance="medium", chapter_number=1):
    return SimpleNamespace(
        event_type=event_type,
        importance=importance,
        chapter_number=chapter_number,
    )


# ============================================================
# 工具函数测试
# ============================================================

class TestSafeCountDict:
    def test_basic_count(self):
        assert _safe_count_dict(["a", "b", "a", "c", "a"]) == {"a": 3, "b": 1, "c": 1}

    def test_skips_none_and_empty(self):
        assert _safe_count_dict([None, "", "a", None, "a"]) == {"a": 2}

    def test_empty_list(self):
        assert _safe_count_dict([]) == {}


class TestNameStyleSignals:
    def test_empty_input(self):
        assert _name_style_signals([]) == {}

    def test_length_distribution(self):
        out = _name_style_signals(["张三", "李四", "王五六", "李逍遥"])
        # 2 字 2 个、3 字 2 个
        assert out["length_distribution"][2] == 2
        assert out["length_distribution"][3] == 2

    def test_chinese_ratio(self):
        out = _name_style_signals(["张三", "Tom", "张飞"])
        # 4 中文 + 3 英文 = 7 总；中文 4/7 ≈ 0.57
        assert 0.5 < out["cn_to_other_ratio"] < 0.7

    def test_top_first_char_diversity(self):
        # 全部以"张"开头：top1 占比 = 1.0
        out = _name_style_signals(["张三", "张飞", "张良"])
        assert out["top_first_char_diversity"] == 1.0


# ============================================================
# EntitiesPatternGenerator 测试
# ============================================================

class TestEntitiesPatternGenerator:
    @pytest.mark.asyncio
    async def test_normal_distribution(self):
        rows = [
            make_entity(name="张三", entity_type="person", role_type="protagonist"),
            make_entity(name="李四", entity_type="person", role_type="supporting"),
            make_entity(name="王五", entity_type="person", role_type="antagonist"),
            make_entity(name="青云山", entity_type="location"),
            make_entity(name="灵石", entity_type="item"),
            make_entity(name="天音宗", entity_type="org"),
        ]
        db = make_db_with_rows(rows)
        gen = EntitiesPatternGenerator()
        out = await gen.generate(db, task_id="task-1")
        assert out is not None
        # 类型分布
        assert out["type_distribution"]["person"] == 3
        assert out["type_distribution"]["location"] == 1
        # role 分布
        assert out["role_distribution"]["protagonist"] == 1
        # 主角原型计数
        assert out["main_role_archetype_count"] == 1
        # 命名风格只看 person
        assert "length_distribution" in out["naming_style_signals"]
        assert out["total_entities"] == 6
        # 不含具体名字（V3 哲学）
        out_str = json.dumps(out, ensure_ascii=False)
        assert "张三" not in out_str
        assert "青云山" not in out_str

    @pytest.mark.asyncio
    async def test_empty_returns_none(self):
        db = make_db_with_rows([])
        gen = EntitiesPatternGenerator()
        out = await gen.generate(db, task_id="task-empty")
        assert out is None

    @pytest.mark.asyncio
    async def test_only_non_person_entities(self):
        # 没 person 类实体时，role_distribution 应为空，命名风格也为空
        rows = [
            make_entity(name="青云山", entity_type="location"),
            make_entity(name="灵石", entity_type="item"),
        ]
        db = make_db_with_rows(rows)
        gen = EntitiesPatternGenerator()
        out = await gen.generate(db, task_id="task-2")
        assert out is not None
        assert out["role_distribution"] == {}
        assert out["naming_style_signals"] == {}
        assert out["main_role_archetype_count"] == 0


# ============================================================
# RelationsPatternGenerator 测试
# ============================================================

class TestRelationsPatternGenerator:
    @pytest.mark.asyncio
    async def test_normal_distribution(self):
        rows = [
            make_relation(category="family", relation_type="father", occurrence=3),
            make_relation(category="family", relation_type="mother", occurrence=2),
            make_relation(category="hostile", relation_type="rival", occurrence=5),
            make_relation(category="intimate", relation_type="lover", occurrence=4),
        ]
        db = make_db_with_rows(rows)
        gen = RelationsPatternGenerator()
        out = await gen.generate(db, task_id="task-1")
        assert out is not None
        assert out["category_distribution"]["family"] == 2
        assert out["category_distribution"]["hostile"] == 1
        # top 关系类型按频次
        assert "rival" in out["top_relation_types"]
        # 平均跨章节强度 (3+2+5+4)/4 = 3.5
        assert out["avg_occurrence_count"] == 3.5
        assert out["total_relations"] == 4

    @pytest.mark.asyncio
    async def test_empty_returns_none(self):
        db = make_db_with_rows([])
        gen = RelationsPatternGenerator()
        out = await gen.generate(db, task_id="task-empty")
        assert out is None


# ============================================================
# EventsPatternGenerator 测试
# ============================================================

class TestEventsPatternGenerator:
    @pytest.mark.asyncio
    async def test_normal_with_density(self):
        rows = [
            make_event(event_type="fight", importance="high", chapter_number=1),
            make_event(event_type="fight", importance="medium", chapter_number=2),
            make_event(event_type="breakthrough", importance="high", chapter_number=5),
            make_event(event_type="meet", importance="low", chapter_number=10),
        ]
        db = make_db_with_rows(rows)
        gen = EventsPatternGenerator()
        out = await gen.generate(db, task_id="task-1")
        assert out is not None
        assert out["type_distribution"]["fight"] == 2
        assert out["importance_distribution"]["high"] == 2
        assert out["importance_distribution"]["medium"] == 1
        # 4 章 / 2 高重要事件 = 2.0
        assert out["high_importance_chapter_density"] == 2.0
        assert out["total_chapters"] == 4
        assert out["total_events"] == 4

    @pytest.mark.asyncio
    async def test_no_high_events_density_is_none(self):
        # 没有 high 事件时，density 应为 None
        rows = [
            make_event(event_type="meet", importance="low", chapter_number=1),
            make_event(event_type="meet", importance="medium", chapter_number=2),
        ]
        db = make_db_with_rows(rows)
        gen = EventsPatternGenerator()
        out = await gen.generate(db, task_id="task-1")
        assert out is not None
        assert out["high_importance_chapter_density"] is None

    @pytest.mark.asyncio
    async def test_empty_returns_none(self):
        db = make_db_with_rows([])
        gen = EventsPatternGenerator()
        out = await gen.generate(db, task_id="task-empty")
        assert out is None


# ============================================================
# build_pattern_dimensions 一站式
# ============================================================

class TestBuildPatternDimensions:
    @pytest.mark.asyncio
    async def test_all_three_dimensions_returned(self, monkeypatch):
        """3 个 generator 都返回 dict 时，输出应是 3 个 JSON 字符串。"""
        # 给三个不同表的查询都 mock 一份对应数据
        # 简化做法：每次 db.execute 调用按顺序返回 entities/relations/events
        call_results = [
            [make_entity(name="A", entity_type="person", role_type="protagonist")],
            [make_relation(category="family", relation_type="father")],
            [make_event(event_type="fight", importance="high", chapter_number=1)],
        ]

        class MockResult:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                m = MagicMock()
                m.all = MagicMock(return_value=self._rows)
                return m

        db = MagicMock()
        db.execute = AsyncMock(side_effect=[MockResult(rs) for rs in call_results])

        out = await build_pattern_dimensions(db, "task-1")
        assert out["entities_json"] is not None
        assert out["relations_json"] is not None
        assert out["events_json"] is not None
        # 反序列化确认是合法 JSON
        ent = json.loads(out["entities_json"])
        assert ent["total_entities"] == 1

    @pytest.mark.asyncio
    async def test_all_empty_returns_all_none(self):
        """所有表都空时，3 列应都为 None（不应抛异常）。"""

        class MockResult:
            def scalars(self):
                m = MagicMock()
                m.all = MagicMock(return_value=[])
                return m

        db = MagicMock()
        db.execute = AsyncMock(return_value=MockResult())

        out = await build_pattern_dimensions(db, "task-empty")
        assert out == {
            "entities_json": None,
            "relations_json": None,
            "events_json": None,
        }

    @pytest.mark.asyncio
    async def test_one_generator_exception_does_not_block_others(self):
        """一个 generator 抛异常不应阻断其他维度。"""
        # 第一次（entities）抛异常，后续正常
        side_effects = [
            RuntimeError("simulated entities query failure"),
            self._mock_result_with([make_relation(category="family", relation_type="father")]),
            self._mock_result_with([make_event(event_type="fight", importance="high", chapter_number=1)]),
        ]

        db = MagicMock()
        db.execute = AsyncMock(side_effect=side_effects)

        out = await build_pattern_dimensions(db, "task-x")
        # entities 因异常应为 None
        assert out["entities_json"] is None
        # relations / events 应正常返回
        assert out["relations_json"] is not None
        assert out["events_json"] is not None

    @staticmethod
    def _mock_result_with(rows):
        class MockResult:
            def scalars(self):
                m = MagicMock()
                m.all = MagicMock(return_value=rows)
                return m

        return MockResult()
