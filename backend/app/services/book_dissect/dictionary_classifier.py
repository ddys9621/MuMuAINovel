"""拆书 V2: 候选词 LLM 分类器（P0）

输入：EntityScanner 产出的 top 100 候选（含频率 + sample_context）
输出：DictionaryEntry 列表（含 entity_type / aliases / confidence）

LLM 调用一次，prompt 模板见 prompts.py:DICTIONARY_CLASSIFICATION_PROMPT_V2。
"""

from __future__ import annotations

import logging
from typing import Optional

from app.services.book_dissect.prompts import (
    DICTIONARY_CLASSIFICATION_PROMPT_V2,
    SYSTEM_PROMPT_V2_DICT,
)
from app.services.book_dissect.v2_types import (
    DictionaryEntry,
    EntityCandidate,
    EntityType,
)
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


_VALID_TYPES = {
    EntityType.PERSON.value,
    EntityType.LOCATION.value,
    EntityType.ITEM.value,
    EntityType.ORG.value,
    EntityType.CONCEPT.value,
}
_VALID_CONFIDENCES = {"high", "medium", "low"}


class DictionaryClassifier:
    """候选词 LLM 分类器。

    用法::

        classifier = DictionaryClassifier(ai_service=ai_service)
        entries = await classifier.classify(candidates, max_candidates=100)
    """

    # ----- 配置常量 -----
    MAX_CANDIDATES_PER_CALL = 100         # 单次 LLM 调用最多分类多少候选
    DEFAULT_TEMPERATURE = 0.2             # 分类任务用低温度
    MAX_TOKENS = 4000                     # LLM 输出预算

    def __init__(self, ai_service):
        """
        Args:
            ai_service: app.services.ai_service.AIService 实例
        """
        self.ai_service = ai_service

    async def classify(
        self,
        candidates: list[EntityCandidate],
        max_candidates: Optional[int] = None,
    ) -> list[DictionaryEntry]:
        """分类候选词。"""
        if not candidates:
            return []

        cap = max_candidates or self.MAX_CANDIDATES_PER_CALL
        sliced = candidates[:cap]

        system_prompt, user_prompt = self._build_prompt(sliced)

        try:
            resp = await self.ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as exc:
            logger.error("[拆书V2-字典分类] LLM 调用失败: %s", exc)
            # 失败时回退：所有候选标 unknown，让 LLM 章节抽取阶段重新过滤
            return self._fallback_unknown(sliced)

        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[拆书V2-字典分类] LLM 返回空内容")
            return self._fallback_unknown(sliced)

        return self._parse_response(content, sliced)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_prompt(self, candidates: list[EntityCandidate]) -> tuple[str, str]:
        """构造 (system_prompt, user_prompt)。"""
        # 候选词 prompt 内容：name | freq | suggested_type | sample_context
        lines = []
        for cand in candidates:
            suggested = cand.suggested_type or "?"
            ctx = (cand.sample_context or "").replace("|", "/")[:60]
            lines.append(
                f"- {cand.name} (频率={cand.frequency}, 建议类型={suggested}, 上下文：{ctx})"
            )
        candidates_text = "\n".join(lines)

        user_prompt = DICTIONARY_CLASSIFICATION_PROMPT_V2.format(
            candidates=candidates_text
        )
        return SYSTEM_PROMPT_V2_DICT, user_prompt

    def _parse_response(
        self,
        raw_text: str,
        candidates: list[EntityCandidate],
    ) -> list[DictionaryEntry]:
        """解析 LLM 输出 JSON 并转换为 DictionaryEntry。"""
        result = safe_parse_json(
            raw_text,
            default=None,
            expected_type="object",
            log_prefix="[拆书V2-字典分类]",
        )
        if not isinstance(result, dict):
            logger.warning("[拆书V2-字典分类] JSON 解析后非 object，回退 unknown")
            return self._fallback_unknown(candidates)

        # 候选词 lookup（用于补全 frequency / sources / sample_context）
        cand_by_name: dict[str, EntityCandidate] = {c.name: c for c in candidates}

        # 1. 解析 entities
        entries_by_name: dict[str, DictionaryEntry] = {}
        rejected_set: set[str] = set()
        # 已被合并到某 canonical 的别名集合（第 4 步要跳过它们，不重新加 unknown）
        merged_aliases: set[str] = set()

        for item in result.get("entities") or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            etype = item.get("type")
            conf = item.get("confidence", "medium")
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            if etype not in _VALID_TYPES:
                # 未知类型按 unknown 处理（仍然保留，让上层决定）
                etype = EntityType.UNKNOWN.value
            if conf not in _VALID_CONFIDENCES:
                conf = "medium"
            cand = cand_by_name.get(name)
            entries_by_name[name] = DictionaryEntry(
                name=name,
                entity_type=etype,
                aliases=[],
                confidence=conf,
                frequency=cand.frequency if cand else 0,
                sources=list(cand.sources) if cand else [],
                sample_context=cand.sample_context if cand else None,
            )

        # 2. 解析 rejected
        for name in result.get("rejected") or []:
            if isinstance(name, str) and name.strip():
                rejected_set.add(name.strip())

        # 3. 应用 alias_groups（注意：仅对 entries_by_name 中存在的 canonical 生效）
        alias_groups = result.get("alias_groups") or []
        for group in alias_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            # 取第一个名字作为 canonical
            canonical = None
            members = []
            for member in group:
                if isinstance(member, str) and member.strip():
                    members.append(member.strip())
            if not members:
                continue
            canonical = members[0]
            # canonical 必须在 entries 中
            if canonical not in entries_by_name:
                # 尝试找一个 members 中存在于 entries 的作为 canonical
                fallback = next((m for m in members if m in entries_by_name), None)
                if fallback is None:
                    continue
                canonical = fallback

            entry = entries_by_name[canonical]
            for member in members:
                if member == canonical:
                    continue
                if member not in entry.aliases:
                    entry.aliases.append(member)
                merged_aliases.add(member)
                # 如果别名也作为独立 entries 出现，移除它（避免重复入库）
                if member in entries_by_name and member != canonical:
                    entries_by_name.pop(member, None)

        # 4. 把 candidates 中"既不在 entries 也不在 rejected 也不在已合并别名"的标 unknown
        #    （LLM 漏判时仍保留信息，让后续 fact_validator 二次过滤）
        for cand in candidates:
            if (
                cand.name in entries_by_name
                or cand.name in rejected_set
                or cand.name in merged_aliases
            ):
                continue
            entries_by_name[cand.name] = DictionaryEntry(
                name=cand.name,
                entity_type=EntityType.UNKNOWN.value,
                aliases=[],
                confidence="low",
                frequency=cand.frequency,
                sources=list(cand.sources),
                sample_context=cand.sample_context,
            )

        # 5. 排序：confidence 高 + frequency 高 优先
        result_list = list(entries_by_name.values())
        result_list.sort(
            key=lambda e: (
                {"high": 3, "medium": 2, "low": 1}.get(e.confidence, 0),
                e.frequency,
            ),
            reverse=True,
        )
        return result_list

    @staticmethod
    def _fallback_unknown(candidates: list[EntityCandidate]) -> list[DictionaryEntry]:
        """LLM 调用 / JSON 解析失败时的兜底：所有候选标 unknown。"""
        return [
            DictionaryEntry(
                name=c.name,
                entity_type=EntityType.UNKNOWN.value,
                aliases=[],
                confidence="low",
                frequency=c.frequency,
                sources=list(c.sources),
                sample_context=c.sample_context,
            )
            for c in candidates
        ]
