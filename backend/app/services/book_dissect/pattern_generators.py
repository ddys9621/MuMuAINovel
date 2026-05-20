"""V3.2-P2：拆书参考包聚合模式三维度生成器（无 LLM）。

设计动机
========
V2 已 LLM 抽好实体/关系/事件，但其原始数据**含具体专有名词**——直接喂 LLM 生成内容
会引导复刻原书人/物/事，违反 V3「学方法不学内容」哲学。

本模块从 V2 三表（book_dissect_entities / relations / events）做纯 SQL 聚合，
输出**类型分布 / 命名风格信号 / 节奏模式**等抽象特征，写入 ReferencePack 三个新列：
- entities_json：实体类型分布 + 角色档案分布 + 命名风格信号
- relations_json：关系类型类别频谱
- events_json：事件类型分布 + 重要性分布 + 节奏密度

设计要点
========
1. 不调 LLM：纯统计聚合，秒级返回，不消耗 token
2. 输出严格不含 canonical_name / 具体事件标题 / 角色名（保 V3 哲学）
3. 命名风格信号采用启发式（字数分布、首末字偏好）而非具体名字
4. 与 5 + 1（synopsis）核心维度并列，由用户在 selector 选择启用

参考：@/agent-docs/features/dissect_to_creation_pipeline.md §A.7
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book_dissect_entity import BookDissectEntity
from app.models.book_dissect_event import BookDissectEvent
from app.models.book_dissect_relation import BookDissectRelation

logger = logging.getLogger(__name__)


# ============================================================
# 公共辅助
# ============================================================

def _safe_count_dict(items: List[Optional[str]]) -> Dict[str, int]:
    """把字段值列表统计成 {value: count} 的字典，跳过 None/空。"""
    cleaned = [v for v in items if v]
    return dict(Counter(cleaned).most_common())


def _name_style_signals(names: List[str]) -> Dict[str, Any]:
    """对 person 类实体的 canonical_name 做命名风格分析（不暴露具体名字）。

    输出抽象信号：
    - length_distribution: 名字字符数分布（例：{2: 35, 3: 50, 4: 12}）
    - top_first_char_diversity: 首字多样性（top1 占比，反映是否有家族姓氏倾向）
    - cn_to_other_ratio: 中文/非中文字符比例（识别玄幻 vs 现代 vs 西幻）
    """
    if not names:
        return {}
    length_dist: Dict[int, int] = {}
    first_chars: List[str] = []
    cn_count = 0
    other_count = 0
    for n in names:
        s = n.strip()
        if not s:
            continue
        length_dist[len(s)] = length_dist.get(len(s), 0) + 1
        first_chars.append(s[0])
        for ch in s:
            if "\u4e00" <= ch <= "\u9fff":
                cn_count += 1
            elif ch.isalpha():
                other_count += 1
    total_chars = cn_count + other_count
    cn_ratio = round(cn_count / total_chars, 2) if total_chars else 0.0
    first_top1_ratio = 0.0
    if first_chars:
        most_common_first_count = Counter(first_chars).most_common(1)[0][1]
        first_top1_ratio = round(most_common_first_count / len(first_chars), 2)
    return {
        # 注意：长度分布 key 是字符数 int，序列化时 JSON 自动转 str
        "length_distribution": length_dist,
        "top_first_char_diversity": first_top1_ratio,
        "cn_to_other_ratio": cn_ratio,
    }


# ============================================================
# 实体聚合
# ============================================================

class EntitiesPatternGenerator:
    """实体类型分布聚合器（不调 LLM）。"""

    async def generate(self, db: AsyncSession, task_id: str) -> Optional[Dict[str, Any]]:
        """聚合 V2 entities 表，输出 entities_json 结构。

        Returns:
            None 表示 V2 数据不足（任务无实体），ReferencePack 列保持 NULL。
        """
        result = await db.execute(
            select(BookDissectEntity).where(BookDissectEntity.task_id == task_id)
        )
        entities = list(result.scalars().all())
        if not entities:
            logger.info(
                "[V3.2-P2 entities] 任务 %s 无实体数据，跳过", task_id[:8]
            )
            return None

        type_dist = _safe_count_dict([e.entity_type for e in entities])
        # 仅 person 实体有 role_type；其它类型不参与
        person_entities = [e for e in entities if e.entity_type == "person"]
        role_dist = _safe_count_dict([e.role_type for e in person_entities])
        # 命名风格仅看 person（避免 location/item 类型干扰，那些有专门规律）
        person_names = [e.canonical_name for e in person_entities if e.canonical_name]
        naming_signals = _name_style_signals(person_names)

        # 主角原型计数（role_type=protagonist 的人）：给后续生成者一个「这本书有几条主线」的提示
        main_role_count = role_dist.get("protagonist", 0)

        out = {
            "type_distribution": type_dist,
            "role_distribution": role_dist,
            "naming_style_signals": naming_signals,
            "main_role_archetype_count": main_role_count,
            "total_entities": len(entities),
        }
        logger.info(
            "[V3.2-P2 entities] task=%s entities=%d types=%s",
            task_id[:8], len(entities), list(type_dist.keys()),
        )
        return out


# ============================================================
# 关系聚合
# ============================================================

class RelationsPatternGenerator:
    """关系类型频谱聚合器（不调 LLM）。"""

    async def generate(self, db: AsyncSession, task_id: str) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(BookDissectRelation).where(BookDissectRelation.task_id == task_id)
        )
        relations = list(result.scalars().all())
        if not relations:
            logger.info(
                "[V3.2-P2 relations] 任务 %s 无关系数据，跳过", task_id[:8]
            )
            return None

        category_dist = _safe_count_dict([r.relation_category for r in relations])
        # top 关系类型（已归一化的字符串）：取前 10 项
        type_counter = Counter([r.relation_type for r in relations if r.relation_type])
        top_types = dict(type_counter.most_common(10))

        # 平均跨章节出现次数（关系强度信号）
        avg_occurrence = (
            round(
                sum((r.occurrence_count or 0) for r in relations) / len(relations),
                2,
            )
            if relations
            else 0.0
        )

        out = {
            "category_distribution": category_dist,
            "top_relation_types": top_types,
            "avg_occurrence_count": avg_occurrence,
            "total_relations": len(relations),
        }
        logger.info(
            "[V3.2-P2 relations] task=%s relations=%d categories=%s",
            task_id[:8], len(relations), list(category_dist.keys()),
        )
        return out


# ============================================================
# 事件聚合
# ============================================================

class EventsPatternGenerator:
    """事件节奏模式聚合器（不调 LLM）。"""

    async def generate(self, db: AsyncSession, task_id: str) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(BookDissectEvent).where(BookDissectEvent.task_id == task_id)
        )
        events = list(result.scalars().all())
        if not events:
            logger.info(
                "[V3.2-P2 events] 任务 %s 无事件数据，跳过", task_id[:8]
            )
            return None

        type_dist = _safe_count_dict([e.event_type for e in events])
        importance_dist = _safe_count_dict([e.importance for e in events])

        # 高重要性事件密度：每多少章一次（high importance event density）
        high_events = [e for e in events if e.importance == "high"]
        chapters = sorted(
            {e.chapter_number for e in events if e.chapter_number is not None}
        )
        total_chapters = len(chapters)
        high_chapter_density = (
            round(total_chapters / len(high_events), 2)
            if high_events and total_chapters
            else None
        )

        out = {
            "type_distribution": type_dist,
            "importance_distribution": importance_dist,
            "high_importance_chapter_density": high_chapter_density,
            "total_chapters": total_chapters,
            "total_events": len(events),
        }
        logger.info(
            "[V3.2-P2 events] task=%s events=%d high=%d density=%s",
            task_id[:8], len(events), len(high_events), high_chapter_density,
        )
        return out


# ============================================================
# 一站式：3 个 generator 串行调用 + 序列化
# ============================================================

async def build_pattern_dimensions(
    db: AsyncSession, task_id: str
) -> Dict[str, Optional[str]]:
    """一次性产出 entities/relations/events 三维度的 JSON 文本（None 表示数据不足）。

    返回 dict 直接对应 ReferencePack 三个列名，便于 extractor_v2 直接 unpack 写入。
    """
    entities_gen = EntitiesPatternGenerator()
    relations_gen = RelationsPatternGenerator()
    events_gen = EventsPatternGenerator()

    out: Dict[str, Optional[str]] = {}
    for col, gen in (
        ("entities_json", entities_gen),
        ("relations_json", relations_gen),
        ("events_json", events_gen),
    ):
        try:
            data = await gen.generate(db, task_id)
            out[col] = json.dumps(data, ensure_ascii=False) if data else None
        except Exception as e:  # pragma: no cover
            logger.warning(
                "[V3.2-P2 %s] task=%s 聚合失败（已忽略）：%s", col, task_id[:8], e
            )
            out[col] = None
    return out
