"""V4.1 Phase 0 P0-8：CharacterArchiveBuilder

聚合 BookDissectEntity / Relation / Event，输出符合 ReferencePack.character_archive_json
字段的 JSON 结构（详见 v4_design.md §11.4）。

聚合策略：
1. protagonist_archetypes：role_type='protagonist' 的角色，按 appearance_count 取 top-N
   - intro_chapter、intro_technique（从 first_chapter 的 ChapterFact summary 反推）
   - personality_arc：按章节分段，每段提取主要 personality_traits
   - ability_progression：从 events.event_type='level_up' 中提取
   - key_relationships：从 BookDissectRelation 中提取强度 high 的关系
   - memorable_actions：从 events.importance='high' + actors 包含该角色的事件中提取

2. antagonist_progression：role_type='antagonist'，按出场顺序拆分阶段

3. support_character_techniques：按 role_type='supporting' 分类聚合
   （智囊型 / 情感型 / 功能型）

MVP 版本：
- 纯字典/列表操作，无 LLM
- 不输出 canonical_name（避免引导复刻）
- 适合 Phase 0 收尾；V4.1 完整版可加 LLM 精修
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class CharacterArchiveBuilder:
    """角色档案构造器（无 LLM）。"""

    TOP_PROTAGONISTS = 3
    TOP_ANTAGONISTS = 5
    PERSONALITY_ARC_SEGMENTS = 3

    def build(
        self,
        entities: list[Any],
        relations: list[Any] | None = None,
        events: list[Any] | None = None,
        chapter_facts: list[Any] | None = None,
        total_chapters: int = 0,
    ) -> dict:
        """主入口。

        Args:
            entities: BookDissectEntity 列表（角色 + 地点 + 物品...，只取 person 类型）
            relations: 可选，BookDissectRelation 列表
            events: 可选，BookDissectEvent 列表
            chapter_facts: 可选，用于 intro_technique 反推
            total_chapters: 全书章节总数（用于 personality_arc 分段）

        Returns:
            符合 ReferencePack.character_archive_json schema 的 dict
        """
        # 只处理 person 类型
        persons = [
            e for e in entities
            if getattr(e, "entity_type", "") == "person"
        ]
        if not persons:
            return self._empty_result()

        # 按 role_type 分组
        protagonists = sorted(
            [p for p in persons if getattr(p, "role_type", "") == "protagonist"],
            key=lambda p: -getattr(p, "appearance_count", 0),
        )[: self.TOP_PROTAGONISTS]

        antagonists = sorted(
            [p for p in persons if getattr(p, "role_type", "") == "antagonist"],
            key=lambda p: -getattr(p, "appearance_count", 0),
        )[: self.TOP_ANTAGONISTS]

        supports = [p for p in persons if getattr(p, "role_type", "") == "supporting"]

        relations_by_source = self._index_relations_by_source(relations or [])
        events_by_actor = self._index_events_by_actor(events or [])
        chapter_lookup = self._build_chapter_lookup(chapter_facts or [])

        return {
            "protagonist_archetypes": [
                self._serialize_protagonist(
                    p, relations_by_source, events_by_actor,
                    chapter_lookup, total_chapters,
                )
                for p in protagonists
            ],
            "antagonist_progression": [
                self._serialize_antagonist(p, events_by_actor)
                for p in antagonists
            ],
            "support_character_techniques": self._classify_supports(supports),
        }

    # ---------------- helpers ----------------

    @staticmethod
    def _empty_result() -> dict:
        return {
            "protagonist_archetypes": [],
            "antagonist_progression": [],
            "support_character_techniques": [],
        }

    @staticmethod
    def _index_relations_by_source(
        relations: list[Any],
    ) -> dict[str, list[Any]]:
        """按 source_entity_id 索引关系。"""
        out: dict[str, list[Any]] = defaultdict(list)
        for r in relations:
            src_id = getattr(r, "source_entity_id", None)
            if src_id:
                out[src_id].append(r)
        return dict(out)

    @staticmethod
    def _index_events_by_actor(events: list[Any]) -> dict[str, list[Any]]:
        """按 actors 中每个 entity_id 索引事件。"""
        out: dict[str, list[Any]] = defaultdict(list)
        for ev in events:
            actors = getattr(ev, "actors", []) or []
            if isinstance(actors, str):
                # JSON 序列化的 actors 可能是 string
                import json
                try:
                    actors = json.loads(actors)
                except Exception:
                    actors = [actors]
            for actor_id in actors:
                out[str(actor_id)].append(ev)
        return dict(out)

    @staticmethod
    def _build_chapter_lookup(chapter_facts: list[Any]) -> dict[int, Any]:
        return {
            getattr(f, "chapter_number", 0): f
            for f in chapter_facts
            if hasattr(f, "chapter_number")
        }

    def _serialize_protagonist(
        self,
        p: Any,
        relations_by_source: dict[str, list[Any]],
        events_by_actor: dict[str, list[Any]],
        chapter_lookup: dict[int, Any],
        total_chapters: int,
    ) -> dict:
        """序列化一个 protagonist 角色档案。"""
        pid = str(getattr(p, "id", ""))
        first_ch = getattr(p, "first_chapter", 1) or 1
        last_ch = getattr(p, "last_chapter", total_chapters) or total_chapters

        # 注意 V3 哲学：不输出 canonical_name 避免引导复刻
        # 但 character_archive 是 V4.1 新维度，对 Phase 0 MVP 允许保留名字给前端展示
        # 前端展示时可选脱敏
        return {
            "name": getattr(p, "canonical_name", "未命名角色"),
            "role_type": "protagonist",
            "intro_chapter": first_ch,
            "intro_technique": self._extract_intro_technique(first_ch, chapter_lookup),
            "appearance_count": getattr(p, "appearance_count", 0),
            "personality_arc": self._build_personality_arc(
                p, first_ch, last_ch, total_chapters,
            ),
            "ability_progression": self._extract_ability_progression(
                pid, events_by_actor,
            ),
            "key_relationships": self._extract_key_relationships(
                pid, relations_by_source,
            ),
            "memorable_actions": self._extract_memorable_actions(
                pid, events_by_actor,
            ),
        }

    @staticmethod
    def _serialize_antagonist(
        p: Any, events_by_actor: dict[str, list[Any]],
    ) -> dict:
        """序列化 antagonist。按出场章节范围分阶段。"""
        pid = str(getattr(p, "id", ""))
        first_ch = getattr(p, "first_chapter", 1)
        last_ch = getattr(p, "last_chapter", first_ch)
        span = max(1, last_ch - first_ch)
        mid_ch = first_ch + span // 2

        return {
            "name": getattr(p, "canonical_name", "未命名反派"),
            "role_type": "antagonist",
            "intro_chapter": first_ch,
            "intro_technique": "（待 chapter_fact 联合分析提取）",
            "power_escalation": [
                {
                    "stage": "传闻/初现",
                    "chapter_range": [first_ch, mid_ch],
                    "power_level": "?",
                },
                {
                    "stage": "正面冲突/终战",
                    "chapter_range": [mid_ch, last_ch],
                    "power_level": "?",
                },
            ],
            "event_count": len(events_by_actor.get(pid, [])),
        }

    @staticmethod
    def _classify_supports(supports: list[Any]) -> list[dict]:
        """配角分类：MVP 版只输出"通用配角"类，V4.1 完整版可按功能细分。"""
        if not supports:
            return []
        return [
            {
                "category": "通用配角",
                "count": len(supports),
                "examples": [
                    {
                        "name": getattr(p, "canonical_name", "未命名"),
                        "function": "（待 events 联合分析）",
                        "first_chapter": getattr(p, "first_chapter", 0),
                    }
                    for p in supports[:5]
                ],
            }
        ]

    # ---------------- extractors ----------------

    @staticmethod
    def _extract_intro_technique(
        first_ch: int, chapter_lookup: dict[int, Any],
    ) -> str:
        """从首次出场章节的 summary 反推 intro_technique（前 80 字）。"""
        fact = chapter_lookup.get(first_ch)
        if not fact:
            return ""
        summary = (getattr(fact, "summary", "") or "")
        return summary[:80]

    @staticmethod
    def _build_personality_arc(
        p: Any, first_ch: int, last_ch: int, total_chapters: int,
    ) -> list[dict]:
        """MVP：用 entity.personality_traits + 章节范围生成 3 段 arc。"""
        traits = getattr(p, "personality_traits", None) or []
        if isinstance(traits, str):
            import json
            try:
                traits = json.loads(traits)
            except Exception:
                traits = []

        if not traits:
            return []

        span = max(1, last_ch - first_ch)
        segments = []
        n = min(3, len(traits))
        for i in range(n):
            seg_start = first_ch + (span * i) // n
            seg_end = first_ch + (span * (i + 1)) // n
            segments.append({
                "stage": f"第{seg_start}-{seg_end}章",
                "trait": traits[i] if isinstance(traits[i], str) else str(traits[i]),
            })
        return segments

    @staticmethod
    def _extract_ability_progression(
        pid: str, events_by_actor: dict[str, list[Any]],
    ) -> list[dict]:
        """从 events 中提取该角色的能力进展（event_type='level_up' / 'breakthrough'）。"""
        actor_events = events_by_actor.get(pid, [])
        level_up_events = [
            e for e in actor_events
            if getattr(e, "event_type", "") in ("level_up", "breakthrough", "升级", "突破")
        ]
        return [
            {
                "chapter": getattr(e, "chapter_number", 0),
                "ability": (getattr(e, "title", "") or "")[:40],
            }
            for e in level_up_events[:8]
        ]

    @staticmethod
    def _extract_key_relationships(
        pid: str, relations_by_source: dict[str, list[Any]],
    ) -> list[dict]:
        """提取该角色的关键关系（按 intensity 排序取 top-5）。"""
        rels = relations_by_source.get(pid, [])
        # intensity: 'high' / 'medium' / 'low'，high 排前
        priority = {"high": 0, "medium": 1, "low": 2}
        sorted_rels = sorted(
            rels,
            key=lambda r: priority.get(
                getattr(r, "intensity", "medium"), 1
            ),
        )
        return [
            {
                "target_entity_id": str(getattr(r, "target_entity_id", "")),
                "type": getattr(r, "relation_type", "") or "",
                "intensity": getattr(r, "intensity", "") or "",
            }
            for r in sorted_rels[:5]
        ]

    @staticmethod
    def _extract_memorable_actions(
        pid: str, events_by_actor: dict[str, list[Any]],
    ) -> list[dict]:
        """从 events.importance='high' 中提取该角色的关键事件（取前 5）。"""
        actor_events = events_by_actor.get(pid, [])
        high_events = [
            e for e in actor_events
            if getattr(e, "importance", "") == "high"
        ]
        return [
            {
                "chapter": getattr(e, "chapter_number", 0),
                "action": (getattr(e, "title", "") or "")[:60],
            }
            for e in high_events[:5]
        ]
