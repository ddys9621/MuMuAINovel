"""拆书 V3.2 - Tab6 故事类型骨架生成器（synopsis 复活）

输入：聚合后的全书结构化数据（EntityProfile + TimelineEvent + 统计）
输出：synopsis dict，包含 8 个抽象维度：
      genre_tag / core_premise / golden_finger_concept / power_system_overview /
      central_conflict / ultimate_goal / selling_points / target_audience_signals

核心设计差异（与 V2 旧版区别）：
- V2 旧版：让 LLM 输出原书的 title/premise/具体设定 → 容易复刻
- V3.2 新版：抽「类型骨架」而非「具体内容」，输出可借鉴的方向参考
- 严示「禁止输出原书具体专有名词」，作为 Story Bible 层的全局引导

参见：@/agent-docs/features/dissect_to_creation_pipeline.md §A.6（synopsis 复活）
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.book_dissect._base_v3_generator import BaseV3Generator
from app.services.book_dissect.event_timeline_builder import TimelineEvent
from app.services.book_dissect.prompts import (
    SYNOPSIS_PROMPT_V3,
    SYSTEM_PROMPT_V3,
)
from app.services.book_dissect.v2_types import EntityProfile

logger = logging.getLogger(__name__)

_LABEL = "[拆书V3.2-梗概]"
_SCHEMA_HINT = (
    "genre_tag, core_premise, golden_finger_concept, power_system_overview, "
    "central_conflict, ultimate_goal, selling_points, target_audience_signals"
)


class SynopsisGenerator(BaseV3Generator):
    """故事类型骨架生成器（V3.2 复活版，原 V2 SynopsisGenerator 已废弃删除）"""

    DEFAULT_TEMPERATURE = 0.4
    MAX_TOKENS = 1800

    TOP_CHARACTERS = 8
    MAX_KEY_EVENTS = 25

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def generate(
        self,
        entities: list[EntityProfile],
        timeline: list[TimelineEvent],
        stats: dict[str, Any],
    ) -> Optional[dict]:
        """主入口。返回 synopsis dict 或 None（生成失败不阻塞其他维度）。"""
        chars = [e for e in entities if e.entity_type == "person"][: self.TOP_CHARACTERS]
        key_events = [
            ev for ev in timeline if ev.importance == "high"
        ][: self.MAX_KEY_EVENTS]

        # 注意：故意只给「角色配置类型」而非具体名字，让 LLM 不易复刻
        chars_text = "\n".join(self._format_char_anonymized(c) for c in chars) or "（无）"
        events_text = "\n".join(self._format_event_anonymized(e) for e in key_events) or "（无）"

        stats_lines = [
            f"- 章节总数：{stats.get('chapter_count', 0)}",
            f"- 全书字数：{stats.get('total_words', 0)}",
            f"- 已抽取章节：{stats.get('chapters_extracted', 0)}",
            f"- 主要角色数：{len(chars)}",
            f"- 高重要性事件数：{len(key_events)}",
        ]
        stats_text = "\n".join(stats_lines)

        user_prompt = SYNOPSIS_PROMPT_V3.format(
            stats=stats_text,
            characters=chars_text,
            key_events=events_text,
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
    def _format_char_anonymized(e: EntityProfile) -> str:
        """匿名化角色信息——只给类型/出场频度，不给具体姓名（防 LLM 复刻）。"""
        role_part = f"（{e.role_type}）" if e.role_type else ""
        return (
            f"- 一个{role_part}型角色，"
            f"出场 {e.appearance_count} 次，"
            f"贯穿章节 {e.first_chapter}-{e.last_chapter}"
        )

    @staticmethod
    def _format_event_anonymized(ev: TimelineEvent) -> str:
        """匿名化事件——只给章节号 + 事件类型，不给具体细节（防 LLM 复刻）。"""
        return f"- 第{ev.chapter_number}章 [{ev.event_type}]"

    @staticmethod
    def _sanitize(d: dict) -> dict:
        """字段清洗：保留 8 维度结构，缺失字段填 None。"""
        EXPECTED_FIELDS = (
            "genre_tag",
            "core_premise",
            "golden_finger_concept",
            "power_system_overview",
            "central_conflict",
            "ultimate_goal",
            "selling_points",
            "target_audience_signals",
        )
        out: dict[str, Any] = {}
        for key in EXPECTED_FIELDS:
            v = d.get(key)
            if key == "selling_points":
                # selling_points 必须为字符串列表
                if isinstance(v, list):
                    out[key] = [
                        s.strip() for s in v if isinstance(s, str) and s.strip()
                    ][:8]  # 最多 8 个，防滥
                else:
                    out[key] = []
            else:
                out[key] = v.strip() if isinstance(v, str) else (v if v is not None else None)
        return out
