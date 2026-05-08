"""拆书 V3 - Tab3 结构手法生成器

输入：章节级事实列表（ChapterFact）+ 总章节数
输出：structure dict，分析开篇 / 中段冲突升级 / 结尾钩三个维度的"如何写"指导

策略：从全部章节中抽取 3 类样本（开篇 3 章 / 中段冲突章 / 结尾 3 章）喂给 LLM，
让 LLM 反推作者的章节级结构手法。

参见：@/agent-docs/features/book_dissect_v3_imitation_design.md §3 Tab3
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.book_dissect.prompts import (
    STRUCTURE_PROMPT_V3,
    SYSTEM_PROMPT_V3,
)
from app.services.book_dissect.v2_types import ChapterFact
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


class StructureGenerator:
    """章节结构手法生成器（Tab3）。"""

    DEFAULT_TEMPERATURE = 0.4
    MAX_TOKENS = 2400

    OPENING_COUNT = 3
    ENDING_COUNT = 3
    MIDPOINT_COUNT = 4

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def generate(self, chapter_facts: list[ChapterFact]) -> Optional[dict]:
        """主入口。"""
        if not chapter_facts:
            logger.warning("[拆书V3-结构] 章节事实为空，跳过")
            return None

        # 按章节号排序
        sorted_facts = sorted(chapter_facts, key=lambda f: f.chapter_number)

        # 三段采样
        opening = sorted_facts[: self.OPENING_COUNT]
        ending = sorted_facts[-self.ENDING_COUNT:] if len(sorted_facts) > self.OPENING_COUNT else []
        midpoint = self._select_midpoint(sorted_facts, opening, ending)

        opening_text = self._format_facts(opening) or "（无）"
        midpoint_text = self._format_facts(midpoint) or "（无）"
        ending_text = self._format_facts(ending) or "（无）"

        prompt = STRUCTURE_PROMPT_V3.format(
            opening_chapters=opening_text,
            midpoint_chapters=midpoint_text,
            ending_chapters=ending_text,
        )

        try:
            resp = await self.ai_service.generate_text(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_V3,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as exc:
            logger.error("[拆书V3-结构] LLM 调用失败: %s", exc)
            return None

        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[拆书V3-结构] LLM 返回空内容")
            return None

        result = safe_parse_json(
            content,
            default=None,
            expected_type="object",
            log_prefix="[拆书V3-结构]",
        )
        if not isinstance(result, dict):
            logger.warning("[拆书V3-结构] JSON 解析非 object")
            return None

        return self._sanitize(result)

    def _select_midpoint(
        self,
        sorted_facts: list[ChapterFact],
        opening: list[ChapterFact],
        ending: list[ChapterFact],
    ) -> list[ChapterFact]:
        """从中段挑选包含 "高重要性" 事件的章节。"""
        opening_nums = {f.chapter_number for f in opening}
        ending_nums = {f.chapter_number for f in ending}
        candidates = [
            f for f in sorted_facts
            if f.chapter_number not in opening_nums
            and f.chapter_number not in ending_nums
        ]
        # 优先含高重要性事件的章节
        scored = [
            (sum(1 for ev in f.events if ev.importance == "high"), f)
            for f in candidates
        ]
        scored.sort(key=lambda x: (-x[0], x[1].chapter_number))
        return [f for _, f in scored[: self.MIDPOINT_COUNT]]

    @staticmethod
    def _format_facts(facts: list[ChapterFact]) -> str:
        """章节摘要 + 关键事件列表。"""
        lines: list[str] = []
        for f in facts:
            lines.append(f"【第{f.chapter_number}章 {f.chapter_title or ''}】")
            if f.summary:
                lines.append(f"摘要：{f.summary}")
            if f.events:
                ev_lines = [
                    f"  - [{ev.importance}] {ev.event_type}: {ev.title}"
                    + (f"（{ev.description}）" if ev.description else "")
                    for ev in f.events[:5]
                ]
                lines.append("事件：")
                lines.extend(ev_lines)
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _sanitize(d: dict) -> dict:
        EXPECTED = ("opening_pattern", "midpoint_conflict_escalation", "ending_hook_pattern")
        out: dict[str, Any] = {}
        for key in EXPECTED:
            sub = d.get(key)
            if isinstance(sub, dict):
                cleaned: dict[str, Any] = {}
                for k, v in sub.items():
                    if v is None:
                        continue
                    if isinstance(v, str):
                        cleaned[k] = v.strip()
                    elif isinstance(v, list):
                        cleaned[k] = [
                            item.strip() if isinstance(item, str) else item
                            for item in v
                            if item
                        ]
                    else:
                        cleaned[k] = v
                out[key] = cleaned
            else:
                out[key] = None
        return out
