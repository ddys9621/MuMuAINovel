"""拆书 V3 - Tab1 写作方法论生成器

输入：聚合后的全书结构化数据（EntityProfile + TimelineEvent + 统计）
输出：methodology dict，包含金手指模式 / 开篇钩 / 打脸节奏 / 升级路线 / 爽点密度
      五个维度的"如何写"指导，**不复刻原书内容**。

调用 LLM 一次。失败时返回 None，由编排器决定是否标 partial。

参见：@/agent-docs/features/book_dissect_v3_imitation_design.md §3 Tab1
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.book_dissect._base_v3_generator import BaseV3Generator
from app.services.book_dissect.event_timeline_builder import TimelineEvent
from app.services.book_dissect.prompts import (
    METHODOLOGY_PROMPT_V3,
    SYSTEM_PROMPT_V3,
)
from app.services.book_dissect.v2_types import EntityProfile

logger = logging.getLogger(__name__)

_LABEL = "[拆书V3-方法论]"
_SCHEMA_HINT = (
    "golden_finger_pattern, opening_hook_pattern, facepunch_rhythm, "
    "power_progression, highlight_density"
)


class MethodologyGenerator(BaseV3Generator):
    """写作方法论生成器（Tab1）"""

    DEFAULT_TEMPERATURE = 0.4
    MAX_TOKENS = 2400

    TOP_CHARACTERS = 10
    TOP_LOCATIONS = 8
    MAX_KEY_EVENTS = 30

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def generate(
        self,
        entities: list[EntityProfile],
        timeline: list[TimelineEvent],
        stats: dict[str, Any],
    ) -> Optional[dict]:
        """主入口。返回 methodology dict 或 None。"""
        # 1. 准备输入文本
        chars = [e for e in entities if e.entity_type == "person"][: self.TOP_CHARACTERS]
        locs = [e for e in entities if e.entity_type == "location"][: self.TOP_LOCATIONS]
        key_events = [
            ev for ev in timeline if ev.importance == "high"
        ][: self.MAX_KEY_EVENTS]

        chars_text = "\n".join(self._format_char(c) for c in chars) or "（无）"
        locs_text = "\n".join(self._format_loc(l) for l in locs) or "（无）"
        events_text = "\n".join(self._format_event(e) for e in key_events) or "（无）"

        stats_lines = [
            f"- 章节总数：{stats.get('chapter_count', 0)}",
            f"- 全书字数：{stats.get('total_words', 0)}",
            f"- 已抽取章节：{stats.get('chapters_extracted', 0)}",
            f"- 主要角色数：{len(chars)}",
            f"- 主要地点数：{len(locs)}",
            f"- 高重要性事件数：{len(key_events)}",
        ]
        stats_text = "\n".join(stats_lines)

        # 2. 调 LLM
        user_prompt = METHODOLOGY_PROMPT_V3.format(
            stats=stats_text,
            characters=chars_text,
            key_events=events_text,
            locations=locs_text,
        )

        result = await self._call_and_parse_object(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT_V3,
            temperature=self.DEFAULT_TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
            label=_LABEL,
            schema_hint=_SCHEMA_HINT,
        )
        if result is None:
            return None
        return self._sanitize(result)

    @staticmethod
    def _format_char(e: EntityProfile) -> str:
        alias_part = f"，别名：{', '.join(e.aliases[:5])}" if e.aliases else ""
        role_part = f"（{e.role_type}）" if e.role_type else ""
        return (
            f"- {e.canonical_name}{role_part}{alias_part}"
            f"，出场 {e.appearance_count} 次，章节 {e.first_chapter}-{e.last_chapter}"
        )

    @staticmethod
    def _format_loc(e: EntityProfile) -> str:
        return f"- {e.canonical_name}，出场 {e.appearance_count} 次"

    @staticmethod
    def _format_event(ev: TimelineEvent) -> str:
        actors = ", ".join(ev.actors[:3]) if ev.actors else "—"
        return f"- 第{ev.chapter_number}章 [{ev.event_type}] {ev.title}（{actors}）"

    @staticmethod
    def _sanitize(d: dict) -> dict:
        """字段清洗：保留五大维度的完整结构，缺失字段填 None / 空值。"""
        EXPECTED_DIMS = (
            "golden_finger_pattern",
            "opening_hook_pattern",
            "facepunch_rhythm",
            "power_progression",
            "highlight_density",
        )
        out: dict[str, Any] = {}
        for dim in EXPECTED_DIMS:
            sub = d.get(dim)
            if isinstance(sub, dict):
                out[dim] = {
                    k: (v.strip() if isinstance(v, str) else v)
                    for k, v in sub.items()
                    if v is not None
                }
            else:
                out[dim] = None
        return out
