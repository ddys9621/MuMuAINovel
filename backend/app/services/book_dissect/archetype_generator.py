"""拆书 V3 - Tab4 角色塑造手法生成器

输入：聚合实体（人物）+ 关系列表
输出：archetypes dict，包含主角 / 配角 / 反派三类的塑造手法分析

核心：**不抽角色本身，抽"作者怎么塑造角色"**。

参见：@/agent-docs/features/book_dissect_v3_imitation_design.md §3 Tab4
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.book_dissect.prompts import (
    ARCHETYPE_PROMPT_V3,
    SYSTEM_PROMPT_V3,
)
from app.services.book_dissect.v2_types import EntityProfile
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


class ArchetypeGenerator:
    """角色塑造手法生成器（Tab4）。"""

    DEFAULT_TEMPERATURE = 0.4
    MAX_TOKENS = 2400

    TOP_SUPPORTING = 6
    TOP_ANTAGONISTS = 4
    TOP_RELATIONS = 20

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def generate(
        self,
        entities: list[EntityProfile],
        relations: list,
    ) -> Optional[dict]:
        """主入口。relations 为聚合后的关系列表（含 person_a / person_b / category）。"""
        persons = [e for e in entities if e.entity_type == "person"]
        if not persons:
            logger.warning("[拆书V3-角色塑造] 无人物实体，跳过")
            return None

        protagonist = next(
            (e for e in persons if e.role_type == "protagonist"),
            persons[0] if persons else None,
        )
        supporting = [e for e in persons if e.role_type == "supporting"][: self.TOP_SUPPORTING]
        antagonists = [e for e in persons if e.role_type == "antagonist"][: self.TOP_ANTAGONISTS]

        prot_text = self._format_one(protagonist) if protagonist else "（无）"
        sup_text = "\n".join(self._format_one(s) for s in supporting) or "（无）"
        ant_text = "\n".join(self._format_one(a) for a in antagonists) or "（无）"
        rel_text = self._format_relations(relations) or "（无）"

        prompt = ARCHETYPE_PROMPT_V3.format(
            protagonist=prot_text,
            supporting=sup_text,
            antagonists=ant_text,
            relations=rel_text,
        )

        try:
            resp = await self.ai_service.generate_text(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_V3,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as exc:
            logger.error("[拆书V3-角色塑造] LLM 调用失败: %s", exc)
            return None

        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[拆书V3-角色塑造] LLM 返回空内容")
            return None

        result = safe_parse_json(
            content,
            default=None,
            expected_type="object",
            log_prefix="[拆书V3-角色塑造]",
        )
        if not isinstance(result, dict):
            logger.warning("[拆书V3-角色塑造] JSON 解析非 object")
            return None

        return self._sanitize(result)

    @staticmethod
    def _format_one(e: EntityProfile) -> str:
        alias_part = f"，别名：{', '.join(e.aliases[:5])}" if e.aliases else ""
        role_part = f"（{e.role_type}）" if e.role_type else ""
        extras = e.profile_extras or {}
        ability_part = ""
        abilities = extras.get("abilities") or []
        if abilities:
            ability_part = f"，能力：{', '.join(abilities[:3])}"
        return (
            f"- {e.canonical_name}{role_part}{alias_part}{ability_part}"
            f"，出场 {e.appearance_count} 次，章节 {e.first_chapter}-{e.last_chapter}"
        )

    def _format_relations(self, relations: list) -> str:
        """关系按出现频次倒序，取 TOP_N。relations 元素需要 .person_a/.person_b/.category/.count。"""
        if not relations:
            return ""
        sorted_rels = sorted(
            relations,
            key=lambda r: getattr(r, "count", 0) or 0,
            reverse=True,
        )[: self.TOP_RELATIONS]
        lines = []
        for r in sorted_rels:
            a = getattr(r, "person_a", "?")
            b = getattr(r, "person_b", "?")
            cat = getattr(r, "category", "其他")
            count = getattr(r, "count", 0) or 0
            lines.append(f"- {a} ↔ {b}（{cat}，章节出现 {count} 次）")
        return "\n".join(lines)

    @staticmethod
    def _sanitize(d: dict) -> dict:
        EXPECTED = ("protagonist_archetype", "supporting_archetype", "antagonist_archetype")
        out: dict[str, Any] = {}
        for key in EXPECTED:
            sub = d.get(key)
            if isinstance(sub, dict):
                out[key] = {
                    k: (v.strip() if isinstance(v, str) else v)
                    for k, v in sub.items()
                    if v is not None
                }
            else:
                out[key] = None
        return out
