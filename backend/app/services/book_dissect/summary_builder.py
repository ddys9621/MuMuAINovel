"""拆书 V2: 前章摘要构建器

为下一章 LLM 抽取构造"已发生事件 + 当前活跃实体"的简要上下文，
保证跨章节实体名一致性，让 LLM 知道"小城" 应该解析为前面已知的"青牛镇"。

输入：已抽取的若干章 ChapterFact + 全书实体词典
输出：硬限制 1500 字符的中文摘要文本
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from app.services.book_dissect.v2_types import ChapterFact, DictionaryEntry, Importance


class SummaryBuilder:
    """前章摘要构建器。"""

    # ----- 配置常量 -----
    PRIOR_CHAPTERS_LOOKBACK = 3          # 向前回溯多少章
    MAX_SUMMARY_CHARS = 1500             # 摘要硬限
    MAX_ACTIVE_CHARACTERS = 12           # 摘要中列出的活跃角色上限
    MAX_KNOWN_LOCATIONS = 8              # 摘要中列出的已知地点上限
    MAX_RECENT_EVENTS = 8                # 摘要中列出的高重要性事件上限

    def build(
        self,
        prior_facts: list[ChapterFact],
        dictionary: Optional[list[DictionaryEntry]] = None,
    ) -> str:
        """构造前章摘要。"""
        if not prior_facts:
            return ""

        recent = prior_facts[-self.PRIOR_CHAPTERS_LOOKBACK:]
        sections: list[str] = []

        # 1. 章节摘要简列
        chapter_summaries = []
        for fact in recent:
            ch_no = fact.chapter_number
            title = fact.chapter_title or ""
            summary = fact.summary or ""
            line = f"第{ch_no}章「{title}」：{summary}".strip()
            if line:
                chapter_summaries.append(line)
        if chapter_summaries:
            sections.append("[最近章节摘要]\n" + "\n".join(chapter_summaries))

        # 2. 活跃角色
        active_chars = self._collect_active_characters(recent)
        if active_chars:
            sections.append("[当前活跃角色] " + " / ".join(active_chars))

        # 3. 关键事件
        recent_events = self._collect_recent_events(recent, self.MAX_RECENT_EVENTS)
        if recent_events:
            sections.append("[最近关键事件]\n" + "\n".join(recent_events))

        # 4. 已知地点
        known_locations = self._collect_known_locations(recent)
        if known_locations:
            sections.append("[已知地点] " + " / ".join(known_locations))

        text = "\n\n".join(sections)
        return self._truncate(text)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _collect_active_characters(self, recent_facts: list[ChapterFact]) -> list[str]:
        """按出场次数倒序，最多 MAX_ACTIVE_CHARACTERS 个。"""
        counter: Counter[str] = Counter()
        for fact in recent_facts:
            for cf in fact.characters:
                if cf.name:
                    counter[cf.name] += 1
        return [name for name, _ in counter.most_common(self.MAX_ACTIVE_CHARACTERS)]

    def _collect_recent_events(
        self,
        recent_facts: list[ChapterFact],
        max_events: int,
    ) -> list[str]:
        """收集最近章的 high importance 事件，不足时补 medium。"""
        high: list[str] = []
        medium: list[str] = []
        for fact in recent_facts:
            for ev in fact.events:
                if not ev.title:
                    continue
                line = f"  · 第{fact.chapter_number}章 [{ev.event_type}] {ev.title}"
                if ev.importance == Importance.HIGH.value:
                    high.append(line)
                elif ev.importance == Importance.MEDIUM.value:
                    medium.append(line)
        merged = high + medium
        return merged[:max_events]

    def _collect_known_locations(self, recent_facts: list[ChapterFact]) -> list[str]:
        """合并最近章节出现的地点（去重保序）。"""
        seen: set[str] = set()
        ordered: list[str] = []
        for fact in recent_facts:
            for loc in fact.locations:
                if not loc.name or loc.name in seen:
                    continue
                seen.add(loc.name)
                ordered.append(loc.name)
                if len(ordered) >= self.MAX_KNOWN_LOCATIONS:
                    return ordered
        return ordered

    def _truncate(self, text: str) -> str:
        """硬截断到 MAX_SUMMARY_CHARS，按句号优先截断。"""
        if len(text) <= self.MAX_SUMMARY_CHARS:
            return text
        head = text[: self.MAX_SUMMARY_CHARS]
        # 尝试按中文句号截断
        last_punct = max(head.rfind("。"), head.rfind("\n"), head.rfind("."))
        if last_punct >= self.MAX_SUMMARY_CHARS // 2:
            return head[: last_punct + 1]
        return head
