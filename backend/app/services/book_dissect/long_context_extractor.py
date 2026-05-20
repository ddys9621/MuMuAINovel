"""拆书 V3.1: 长上下文一次抽取器

把整本书一次性塞给 LLM，返回 list[ChapterFact]。
与 ChapterFactExtractor（逐章版）的关键差异：
- 跳过 EntityScanner / DictionaryClassifier（LLM 自己看完全书做共指）
- 1 次 LLM 调用产出全书 ChapterFact 数组
- 不需要 prior_summary 注入（全书都在 prompt 里）

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4

业界证据：
- NovelHopQA 2025：完整上下文 + 强模型 EM>95%
- LaRA ICML 2025：32k 内长上下文 ≥ RAG，128k 持平

调用前置：必须先经 LongContextRouter.decide() 判定 use_long_context=True，
否则应走逐章流水线。
"""

from __future__ import annotations

import logging
from typing import Optional

from app.services.book_dissect.chapter_fact_extractor import (
    _get_str,
    _parse_characters,
    _parse_concepts,
    _parse_events,
    _parse_items,
    _parse_locations,
    _parse_orgs,
    _parse_relationships,
)
from app.services.book_dissect.chapter_splitter import Chapter
from app.services.book_dissect.prompts import (
    LONG_CONTEXT_EXTRACT_PROMPT,
    SYSTEM_PROMPT_V31_LONG_CONTEXT,
)
from app.services.book_dissect.v2_types import ChapterFact
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


class LongContextExtractionError(Exception):
    """长上下文抽取彻底失败（LLM 调用 / JSON 解析）。"""


class LongContextExtractor:
    """整本书一次性抽取 ChapterFact 列表。"""

    DEFAULT_TEMPERATURE = 0.1
    # 大模型输出预算，但不会真的占满 200k+ ctx 的 45%；按章节数动态加成
    BASE_MAX_TOKENS = 16_000
    MAX_TOKENS_PER_CHAPTER = 600   # 每章预留输出 token
    MAX_TOKENS_HARD_CAP = 64_000   # 硬上限

    # 章节边界标记，与 prompt 中的 "=== 第 N 章 标题 ===" 对齐
    BOUNDARY_TEMPLATE = "=== 第 {n} 章 {title} ==="

    def __init__(self, ai_service):
        """
        Args:
            ai_service: app.services.ai_service.AIService 实例
        """
        self.ai_service = ai_service

    async def extract_all(
        self,
        chapters: list[Chapter],
    ) -> list[ChapterFact]:
        """主入口：一次 LLM 调用产出全书 ChapterFact。

        Args:
            chapters: 章节列表（必须非空，且预先经 LongContextRouter 判定可走）

        Returns:
            list[ChapterFact]，按 chapter_number 升序，长度 = len(chapters)
            漏给的章节用空 ChapterFact 填充

        Raises:
            LongContextExtractionError: LLM 调用失败 / 返回非 JSON 等彻底失败
        """
        if not chapters:
            return []

        full_text = self._build_full_text(chapters)
        user_prompt = LONG_CONTEXT_EXTRACT_PROMPT.format(full_text=full_text)

        max_tokens = self._compute_max_tokens(len(chapters))

        try:
            resp = await self.ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT_V31_LONG_CONTEXT,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.error("[拆书V3.1-长上下文] LLM 调用失败: %s", exc)
            raise LongContextExtractionError(
                f"long-context LLM call failed: {exc}"
            ) from exc

        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[拆书V3.1-长上下文] LLM 返回空内容")
            raise LongContextExtractionError("long-context LLM returned empty content")

        return self._parse_response(content, chapters)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_full_text(self, chapters: list[Chapter]) -> str:
        """用边界标记拼接所有章节正文。"""
        parts: list[str] = []
        for ch in chapters:
            title = ch.title or ch.raw_title or ""
            boundary = self.BOUNDARY_TEMPLATE.format(n=ch.chapter_number, title=title)
            content = (ch.content or "").strip()
            parts.append(boundary)
            if content:
                parts.append(content)
        return "\n\n".join(parts)

    def _compute_max_tokens(self, chapter_count: int) -> int:
        """按章节数动态计算 max_tokens。"""
        budget = self.BASE_MAX_TOKENS + chapter_count * self.MAX_TOKENS_PER_CHAPTER
        return min(budget, self.MAX_TOKENS_HARD_CAP)

    def _parse_response(
        self,
        raw_text: str,
        input_chapters: list[Chapter],
    ) -> list[ChapterFact]:
        """解析 LLM 输出为 ChapterFact 列表。漏给的章节用空 ChapterFact 填补。"""
        result = safe_parse_json(
            raw_text,
            default=None,
            expected_type="object",
            log_prefix="[拆书V3.1-长上下文]",
        )
        if not isinstance(result, dict):
            logger.warning("[拆书V3.1-长上下文] JSON 解析非 object")
            raise LongContextExtractionError("long-context response not a JSON object")

        items = result.get("chapters")
        if not isinstance(items, list):
            logger.warning("[拆书V3.1-长上下文] chapters 字段非 list")
            raise LongContextExtractionError("long-context response missing 'chapters' list")

        # 按 chapter_number 索引：LLM 给的章节
        by_num: dict[int, ChapterFact] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            num_raw = item.get("chapter_number")
            try:
                num = int(num_raw)
            except (TypeError, ValueError):
                logger.debug(
                    "[拆书V3.1-长上下文] 跳过 chapter_number 非整数: %r", num_raw
                )
                continue

            fact = ChapterFact(
                chapter_number=num,
                chapter_title=_get_str(item, "chapter_title"),
                summary=_get_str(item, "summary"),
                characters=_parse_characters(item.get("characters")),
                relationships=_parse_relationships(item.get("relationships")),
                locations=_parse_locations(item.get("locations")),
                events=_parse_events(item.get("events")),
                item_events=_parse_items(item.get("item_events")),
                org_events=_parse_orgs(item.get("org_events")),
                new_concepts=_parse_concepts(item.get("new_concepts")),
            )
            by_num[num] = fact

        # 按输入章节顺序产出，漏给的用空 ChapterFact 填补
        out: list[ChapterFact] = []
        missing: list[int] = []
        for ch in input_chapters:
            f = by_num.get(ch.chapter_number)
            if f is None:
                # LLM 漏给：用空 ChapterFact 占位（保留 chapter_title 便于后续审查）
                out.append(ChapterFact(
                    chapter_number=ch.chapter_number,
                    chapter_title=ch.title or ch.raw_title or "",
                ))
                missing.append(ch.chapter_number)
                continue
            # LLM 给了但 chapter_title 可能空，从输入兜底
            if not f.chapter_title:
                f.chapter_title = ch.title or ch.raw_title or ""
            out.append(f)

        # 排序：按 chapter_number 升序（防 LLM 乱序）
        out.sort(key=lambda f: f.chapter_number)

        if missing:
            logger.warning(
                "[拆书V3.1-长上下文] LLM 漏给 %d 章，使用空 ChapterFact 占位: %s",
                len(missing),
                missing[:10] + (["..."] if len(missing) > 10 else []),
            )

        # 计算非空章节占比，过低则抛错（聚合层兜底无意义）
        non_empty = sum(
            1 for f in out
            if f.summary or f.characters or f.events or f.locations
        )
        if non_empty == 0:
            raise LongContextExtractionError(
                "long-context response yielded no usable chapter facts"
            )
        coverage = non_empty / len(out) if out else 0
        if coverage < 0.3:
            logger.warning(
                "[拆书V3.1-长上下文] 章节有效抽取覆盖率仅 %.1f%%，可能需要切回逐章模式",
                coverage * 100,
            )

        return out
