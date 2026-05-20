"""拆书 V2: 事件时间线构建器（Phase 5）

把所有 ChapterFact.events 按章节序聚合并归一化 actor 名字。

输入：
- chapter_facts: list[ChapterFact]
- alias_map: dict[name -> canonical_name]

输出：list[TimelineEvent]（按 chapter_number 排序）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.services.book_dissect.v2_types import ChapterFact


@dataclass
class TimelineEvent:
    """聚合后的事件。"""

    chapter_number: int
    event_type: str
    title: str
    description: Optional[str] = None
    actors: list[str] = field(default_factory=list)
    location: Optional[str] = None
    importance: str = "medium"
    evidence: Optional[str] = None


class EventTimelineBuilder:
    """事件时间线构建。"""

    def build(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
    ) -> list[TimelineEvent]:
        """主入口。"""
        result: list[TimelineEvent] = []

        for fact in chapter_facts:
            for ev in fact.events:
                actors_canon = []
                for a in ev.actors:
                    canon = alias_map.get(a, a)
                    if canon and canon not in actors_canon:
                        actors_canon.append(canon)
                location_canon = (
                    alias_map.get(ev.location, ev.location) if ev.location else None
                )
                result.append(TimelineEvent(
                    chapter_number=fact.chapter_number,
                    event_type=ev.event_type,
                    title=ev.title,
                    description=ev.description,
                    actors=actors_canon,
                    location=location_canon,
                    importance=ev.importance,
                    evidence=ev.evidence,
                ))

        # 按章节序 + importance 排序
        importance_order = {"high": 0, "medium": 1, "low": 2}
        result.sort(
            key=lambda e: (
                e.chapter_number,
                importance_order.get(e.importance, 99),
            )
        )
        return result
