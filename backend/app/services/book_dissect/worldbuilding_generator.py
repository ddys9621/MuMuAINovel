"""拆书 V3 - Tab5 世界观建模生成器

输入：聚合实体（地点 + 组织 + 概念）+ 父子层级映射
输出：worldbuilding dict，包含时代设计 / 地点层级 / 规则平衡三个维度的"如何写"指导

核心：**不抽世界本身，抽"作者怎么搭建这种世界"**。

参见：@/agent-docs/features/book_dissect_v3_imitation_design.md §3 Tab5
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.book_dissect._base_v3_generator import BaseV3Generator
from app.services.book_dissect.prompts import (
    SYSTEM_PROMPT_V3,
    WORLDBUILDING_PROMPT_V3,
)
from app.services.book_dissect.v2_types import EntityProfile

logger = logging.getLogger(__name__)

_LABEL = "[拆书V3-世界观]"
_SCHEMA_HINT = (
    "era_design, location_hierarchy_design, rule_balance_design"
)


class WorldbuildingGenerator(BaseV3Generator):
    """世界观建模生成器（Tab5）。"""

    DEFAULT_TEMPERATURE = 0.4
    MAX_TOKENS = 2200

    TOP_LOCATIONS = 12
    TOP_ORGS = 8
    TOP_CONCEPTS = 10

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def generate(
        self,
        entities: list[EntityProfile],
        parent_map: Optional[dict[str, Optional[str]]] = None,
    ) -> Optional[dict]:
        """主入口。parent_map 是地点 canonical_name 到 parent name 的映射（来自 LocationHierarchyBuilder）。"""
        locations = [e for e in entities if e.entity_type == "location"][: self.TOP_LOCATIONS]
        orgs = [e for e in entities if e.entity_type == "org"][: self.TOP_ORGS]
        concepts = [e for e in entities if e.entity_type == "concept"][: self.TOP_CONCEPTS]
        items = [e for e in entities if e.entity_type == "item"][:10]

        if not (locations or orgs or concepts):
            logger.warning("[拆书V3-世界观] 无地点/组织/概念实体，跳过")
            return None

        loc_text = self._format_locations(locations, parent_map or {}) or "（无）"
        org_text = self._format_orgs(orgs) or "（无）"
        rule_text = self._format_rule_clues(concepts, items) or "（无）"

        prompt = WORLDBUILDING_PROMPT_V3.format(
            location_tree=loc_text,
            organizations=org_text,
            rule_clues=rule_text,
        )

        result = await self._call_and_parse_object(
            prompt=prompt,
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
    def _format_locations(
        locations: list[EntityProfile],
        parent_map: dict[str, Optional[str]],
    ) -> str:
        """以缩进树形展示地点层级（最多 3 层）。"""
        if not locations:
            return ""
        # 找根节点（parent 为 None 或不在 locations 集合中的）
        loc_names = {e.canonical_name for e in locations}
        roots: list[EntityProfile] = []
        children_map: dict[str, list[EntityProfile]] = {}
        for e in locations:
            parent = parent_map.get(e.canonical_name)
            if parent and parent in loc_names:
                children_map.setdefault(parent, []).append(e)
            else:
                roots.append(e)

        lines: list[str] = []

        def _emit(node: EntityProfile, depth: int) -> None:
            indent = "  " * depth
            lines.append(f"{indent}- {node.canonical_name}（出场 {node.appearance_count} 次）")
            if depth < 3:
                for child in children_map.get(node.canonical_name, []):
                    _emit(child, depth + 1)

        for r in roots:
            _emit(r, 0)
        return "\n".join(lines)

    @staticmethod
    def _format_orgs(orgs: list[EntityProfile]) -> str:
        if not orgs:
            return ""
        return "\n".join(
            f"- {o.canonical_name}（出场 {o.appearance_count} 次）"
            for o in orgs
        )

    @staticmethod
    def _format_rule_clues(
        concepts: list[EntityProfile],
        items: list[EntityProfile],
    ) -> str:
        """从概念（境界/术语/世界规则）+ 关键道具中提取规则线索。"""
        lines: list[str] = []
        if concepts:
            lines.append("【世界概念 / 术语】")
            for c in concepts:
                desc = c.profile_extras.get("description") if c.profile_extras else None
                desc_part = f"：{desc}" if desc else ""
                lines.append(f"- {c.canonical_name}{desc_part}")
        if items:
            if lines:
                lines.append("")
            lines.append("【关键道具】")
            for it in items:
                kind = it.profile_extras.get("type") if it.profile_extras else None
                kind_part = f"（{kind}）" if kind else ""
                lines.append(f"- {it.canonical_name}{kind_part}")
        return "\n".join(lines)

    @staticmethod
    def _sanitize(d: dict) -> dict:
        EXPECTED = ("era_design", "location_hierarchy_design", "rule_balance_design")
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
