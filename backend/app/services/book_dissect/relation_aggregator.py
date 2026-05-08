"""拆书 V2: 关系聚合器（Phase 5）

输入：
- chapter_facts: list[ChapterFact]（已经过 FactValidator）
- alias_map: dict[name -> canonical_name]
- entities: list[EntityProfile]（提供 canonical 集合）

输出：list[AggregatedRelation]（A→B + 类别 + 跨章证据）

聚合策略：
- 关系类别归一化：把"师徒"/"师傅"/"师父"等归到 hierarchical
- 跨章节同关系合并：(canonical_a, canonical_b, category) 累计 occurrence_count
- 端点必须都在 entities 集合（否则丢弃）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.services.book_dissect.v2_types import (
    ChapterFact,
    EntityProfile,
    RelationCategory,
)


# ---------------------------------------------------------------------------
# 关系语义归一化
# ---------------------------------------------------------------------------


_RELATION_KEYWORD_GROUPS: list[tuple[set[str], str]] = [
    # family
    ({"父子", "父女", "母子", "母女", "兄弟", "姐妹", "兄妹", "姊妹",
      "亲子", "祖孙", "叔侄", "舅甥", "姑侄", "堂兄弟", "表兄弟", "家人", "亲属",
      "父", "母", "爹", "娘"}, RelationCategory.FAMILY.value),
    # intimate
    ({"夫妻", "情侣", "恋人", "夫君", "妻子", "未婚妻", "未婚夫",
      "妾室", "情人", "意中人", "伴侣"}, RelationCategory.INTIMATE.value),
    # hierarchical
    ({"师徒", "师父", "师傅", "师尊", "师兄", "师弟", "师姐", "师妹",
      "弟子", "门徒", "上下级", "上司", "下属", "君臣", "主仆", "主人", "仆人",
      "随从", "家丁", "门客", "首领", "属下", "部下"}, RelationCategory.HIERARCHICAL.value),
    # social
    ({"朋友", "好友", "知交", "知己", "盟友", "结义", "结拜", "义兄",
      "义弟", "义父", "义子", "同门", "同宗", "同窗", "同学", "邻居"},
     RelationCategory.SOCIAL.value),
    # hostile
    ({"敌对", "仇敌", "宿敌", "仇人", "敌人", "对头", "情敌", "杀父仇人",
      "竞争", "对手"}, RelationCategory.HOSTILE.value),
]


# 拍平后按长度倒序：长关键字（如"师父"）优先于短关键字（如"父"）匹配，
# 避免"师父"被归到 family。
_KEYWORD_ORDERED: list[tuple[str, str]] = sorted(
    [
        (kw, cat)
        for kws, cat in _RELATION_KEYWORD_GROUPS
        for kw in kws
    ],
    key=lambda x: len(x[0]),
    reverse=True,
)


def normalize_relation_category(relation_type: str) -> str:
    """根据 LLM 原始 relation_type 文本判定类别。

    关键字按长度倒序匹配——"师父" 优先于 "父"；"杀父仇人" 优先于 "仇人" / "父"。
    """
    if not relation_type:
        return RelationCategory.OTHER.value
    rt = relation_type.strip()
    for kw, cat in _KEYWORD_ORDERED:
        if kw in rt:
            return cat
    return RelationCategory.OTHER.value


# ---------------------------------------------------------------------------
# 聚合产物
# ---------------------------------------------------------------------------


@dataclass
class AggregatedRelation:
    """聚合后的关系。"""

    entity_a: str                                      # canonical_name
    entity_b: str                                      # canonical_name
    relation_type: str                                 # 取首次出现的 LLM 输出原文
    relation_category: str                             # family/intimate/hierarchical/social/hostile/other
    evidence: list[dict] = field(default_factory=list)  # [{"chapter": int, "text": str}]
    occurrence_count: int = 0
    first_chapter: Optional[int] = None


class RelationAggregator:
    """关系聚合器。"""

    def aggregate(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
        entities: list[EntityProfile],
    ) -> list[AggregatedRelation]:
        """主入口。"""
        valid_canon = {e.canonical_name for e in entities}
        # key = (canonical_a, canonical_b, category)
        merged: dict[tuple[str, str, str], AggregatedRelation] = {}

        for fact in chapter_facts:
            for rel in fact.relationships:
                canon_a = alias_map.get(rel.person_a, rel.person_a)
                canon_b = alias_map.get(rel.person_b, rel.person_b)
                if canon_a == canon_b:
                    continue
                # 端点必须都聚合实体
                if canon_a not in valid_canon or canon_b not in valid_canon:
                    continue

                category = normalize_relation_category(rel.relation_type)
                key = (canon_a, canon_b, category)

                existing = merged.get(key)
                if existing is None:
                    existing = AggregatedRelation(
                        entity_a=canon_a,
                        entity_b=canon_b,
                        relation_type=rel.relation_type,
                        relation_category=category,
                        evidence=[],
                        occurrence_count=0,
                        first_chapter=fact.chapter_number,
                    )
                    merged[key] = existing
                existing.occurrence_count += 1
                if existing.first_chapter is None or fact.chapter_number < existing.first_chapter:
                    existing.first_chapter = fact.chapter_number
                if rel.evidence:
                    existing.evidence.append({
                        "chapter": fact.chapter_number,
                        "text": rel.evidence,
                    })

        # 排序：按 occurrence_count 倒序，相同时按 first_chapter
        result = list(merged.values())
        result.sort(key=lambda r: (-r.occurrence_count, r.first_chapter or 99999))
        return result
