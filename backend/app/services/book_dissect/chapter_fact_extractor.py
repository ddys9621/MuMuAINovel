"""拆书 V2: 章节级事实抽取器（核心 LLM 调用）

每章一次或多次 LLM 调用，输出严格 JSON 的 ChapterFact。

特性：
- 长章节段落级切分（>7000 字符切 2 段，>12000 字符切 3 段，按 \\n 边界）
- 多段抽取后自动合并 ChapterFact
- LLM 输出非 JSON 时由 safe_parse_json 兜底
- 单章失败返回带 extraction_failed 标记的空 ChapterFact，不阻断后续章节
"""

from __future__ import annotations

import logging
from dataclasses import asdict, fields, is_dataclass
from typing import Any, Optional

from app.services.book_dissect.prompts import (
    CHAPTER_FACT_PROMPT_V2,
    SYSTEM_PROMPT_V2_CHAPTER,
)
from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    ConceptFact,
    DictionaryEntry,
    EventFact,
    Importance,
    ItemFact,
    LocationFact,
    OrgFact,
    RelationFact,
)
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


class ChapterExtractionError(Exception):
    """章节抽取彻底失败（LLM 调用 / JSON 解析）。"""


class ChapterFactExtractor:
    """章节级事实抽取器。"""

    # ----- 长章节切分阈值 -----
    SEGMENT_THRESHOLD_2 = 7000          # >7000 字切 2 段
    SEGMENT_THRESHOLD_3 = 12000         # >12000 字切 3 段
    HARD_LIMIT_PER_CALL = 8000          # 单次 LLM prompt 内容硬限

    # ----- 注入字典限制 -----
    DICTIONARY_TOP_N = 50               # 注入字典时只取 top N 实体

    # ----- LLM 参数 -----
    DEFAULT_TEMPERATURE = 0.2
    MAX_TOKENS = 4000

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def extract(
        self,
        chapter_number: int,
        chapter_title: str,
        chapter_text: str,
        dictionary: list[DictionaryEntry],
        prior_summary: Optional[str] = None,
    ) -> ChapterFact:
        """单章抽取主入口。"""
        if not chapter_text or not chapter_text.strip():
            return ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title)

        segments = self._split_long_chapter(chapter_text)
        segment_facts: list[ChapterFact] = []
        any_success = False
        for i, seg in enumerate(segments, start=1):
            seg_label = f"{chapter_number}.{i}/{len(segments)}" if len(segments) > 1 else f"{chapter_number}"
            fact, ok = await self._extract_one_segment(
                segment_label=seg_label,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                segment_text=seg,
                dictionary=dictionary,
                prior_summary=prior_summary,
            )
            segment_facts.append(fact)
            if ok:
                any_success = True

        if not any_success:
            # 所有段都失败：LLM 调用失败 / 内容为空 / JSON 无法解析
            raise ChapterExtractionError(
                f"chapter {chapter_number} extraction failed for all segments"
            )

        if len(segment_facts) == 1:
            return segment_facts[0]
        return self._merge_segment_facts(segment_facts, chapter_number, chapter_title)

    # ------------------------------------------------------------------
    # 单段抽取
    # ------------------------------------------------------------------

    async def _extract_one_segment(
        self,
        segment_label: str,
        chapter_number: int,
        chapter_title: str,
        segment_text: str,
        dictionary: list[DictionaryEntry],
        prior_summary: Optional[str],
    ) -> tuple[ChapterFact, bool]:
        """返回 (fact, parse_ok)。parse_ok=False 表示 LLM 调用 / JSON 解析彻底失败。"""
        sys_prompt, user_prompt = self._build_prompt(
            chapter_title=chapter_title,
            chapter_text=segment_text,
            dictionary=dictionary,
            prior_summary=prior_summary,
        )

        try:
            resp = await self.ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=sys_prompt,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as exc:
            logger.error("[拆书V2-章节抽取-%s] LLM 调用失败: %s", segment_label, exc)
            return (
                ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title),
                False,
            )

        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[拆书V2-章节抽取-%s] LLM 返回空内容", segment_label)
            return (
                ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title),
                False,
            )

        # 解析 JSON：成功返回非空 dict 才算 ok（即便所有业务字段都为空）
        result = safe_parse_json(
            content,
            default=None,
            expected_type="object",
            log_prefix=f"[拆书V2-章节抽取-{segment_label}]",
        )
        if not isinstance(result, dict):
            logger.warning(
                "[拆书V2-章节抽取-%s] JSON 解析非 object，回退空", segment_label
            )
            return (
                ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title),
                False,
            )

        fact = ChapterFact(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            summary=_get_str(result, "summary"),
            characters=_parse_characters(result.get("characters")),
            relationships=_parse_relationships(result.get("relationships")),
            locations=_parse_locations(result.get("locations")),
            events=_parse_events(result.get("events")),
            item_events=_parse_items(result.get("item_events")),
            org_events=_parse_orgs(result.get("org_events")),
            new_concepts=_parse_concepts(result.get("new_concepts")),
        )
        return fact, True

    # ------------------------------------------------------------------
    # 长章节切分
    # ------------------------------------------------------------------

    @classmethod
    def _split_long_chapter(cls, text: str) -> list[str]:
        """按 \\n 边界把超长章节切成 1-3 段。"""
        n = len(text)
        if n <= cls.SEGMENT_THRESHOLD_2:
            return [text]

        if n <= cls.SEGMENT_THRESHOLD_3:
            target = n // 2
            split_at = cls._find_paragraph_break(text, target)
            return [text[:split_at], text[split_at:]]

        # 切 3 段
        t1 = cls._find_paragraph_break(text, n // 3)
        t2 = cls._find_paragraph_break(text, 2 * n // 3)
        if t2 <= t1:
            t2 = min(n, t1 + (n - t1) // 2)
        return [text[:t1], text[t1:t2], text[t2:]]

    @staticmethod
    def _find_paragraph_break(text: str, target: int) -> int:
        """在 target 附近找最近的 \\n（向前 / 向后 800 字符内）。"""
        radius = 800
        lo = max(0, target - radius)
        hi = min(len(text), target + radius)
        # 优先向后找
        forward = text.find("\n", target, hi)
        if forward != -1:
            return forward + 1
        # 向前找
        backward = text.rfind("\n", lo, target)
        if backward != -1:
            return backward + 1
        # 没换行，硬切
        return target

    # ------------------------------------------------------------------
    # Prompt 构造
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        chapter_title: str,
        chapter_text: str,
        dictionary: list[DictionaryEntry],
        prior_summary: Optional[str],
    ) -> tuple[str, str]:
        # 字典注入：top N 实体的 name + entity_type + aliases
        dict_lines = []
        for entry in (dictionary or [])[: self.DICTIONARY_TOP_N]:
            if entry.entity_type in ("rejected", "unknown"):
                continue
            alias_part = f" (别名：{', '.join(entry.aliases)})" if entry.aliases else ""
            dict_lines.append(f"- {entry.name} [{entry.entity_type}]{alias_part}")
        dictionary_context = (
            "【全书已知实体（请优先复用这些规范名）】\n" + "\n".join(dict_lines)
            if dict_lines
            else ""
        )

        prior_context = (
            "【前章已发生情节摘要】\n" + prior_summary
            if prior_summary
            else ""
        )

        # 硬限内容长度
        if len(chapter_text) > self.HARD_LIMIT_PER_CALL:
            chapter_text = chapter_text[: self.HARD_LIMIT_PER_CALL]

        user_prompt = CHAPTER_FACT_PROMPT_V2.format(
            prior_context=prior_context,
            dictionary_context=dictionary_context,
            chapter_title=chapter_title or "（无标题）",
            chapter_text=chapter_text,
        )
        return SYSTEM_PROMPT_V2_CHAPTER, user_prompt

    # ------------------------------------------------------------------
    # 响应解析
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw_text: str,
        chapter_number: int,
        chapter_title: str,
    ) -> ChapterFact:
        """容错解析 LLM 输出 JSON 为 ChapterFact。失败时返回空 ChapterFact。"""
        result = safe_parse_json(
            raw_text,
            default=None,
            expected_type="object",
            log_prefix=f"[拆书V2-章节抽取-{chapter_number}]",
        )
        if not isinstance(result, dict):
            logger.warning(
                "[拆书V2-章节抽取-%s] JSON 解析非 object，回退空", chapter_number
            )
            return ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title)

        return ChapterFact(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            summary=_get_str(result, "summary"),
            characters=_parse_characters(result.get("characters")),
            relationships=_parse_relationships(result.get("relationships")),
            locations=_parse_locations(result.get("locations")),
            events=_parse_events(result.get("events")),
            item_events=_parse_items(result.get("item_events")),
            org_events=_parse_orgs(result.get("org_events")),
            new_concepts=_parse_concepts(result.get("new_concepts")),
        )

    # ------------------------------------------------------------------
    # 多段合并
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_segment_facts(
        facts: list[ChapterFact],
        chapter_number: int,
        chapter_title: str,
    ) -> ChapterFact:
        """合并同章多段。"""
        if not facts:
            return ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title)

        merged = ChapterFact(chapter_number=chapter_number, chapter_title=chapter_title)

        # summary：拼接非空段
        summaries = [f.summary for f in facts if f.summary]
        if summaries:
            merged.summary = " ".join(summaries)[:300]

        # characters：按 name 合并
        char_by_name: dict[str, CharacterFact] = {}
        for f in facts:
            for cf in f.characters:
                existing = char_by_name.get(cf.name)
                if not existing:
                    char_by_name[cf.name] = CharacterFact(
                        name=cf.name,
                        new_aliases=list(cf.new_aliases),
                        role_hint=cf.role_hint,
                        appearance=cf.appearance,
                        abilities_gained=list(cf.abilities_gained),
                        locations_in_chapter=list(cf.locations_in_chapter),
                        evidence=cf.evidence,
                    )
                    continue
                # 合并 list 字段（去重）
                for alias in cf.new_aliases:
                    if alias not in existing.new_aliases:
                        existing.new_aliases.append(alias)
                for ab in cf.abilities_gained:
                    if ab not in existing.abilities_gained:
                        existing.abilities_gained.append(ab)
                for loc in cf.locations_in_chapter:
                    if loc not in existing.locations_in_chapter:
                        existing.locations_in_chapter.append(loc)
                # 单值字段：取已有 / 否则用新值
                existing.appearance = existing.appearance or cf.appearance
                existing.role_hint = existing.role_hint or cf.role_hint
                existing.evidence = existing.evidence or cf.evidence
        merged.characters = list(char_by_name.values())

        # relationships：按 (a, b, type) 去重
        rel_seen: set[tuple[str, str, str]] = set()
        for f in facts:
            for r in f.relationships:
                key = (r.person_a, r.person_b, r.relation_type)
                if key in rel_seen:
                    continue
                rel_seen.add(key)
                merged.relationships.append(r)

        # locations：按 name 合并
        loc_by_name: dict[str, LocationFact] = {}
        for f in facts:
            for loc in f.locations:
                existing = loc_by_name.get(loc.name)
                if not existing:
                    loc_by_name[loc.name] = LocationFact(
                        name=loc.name,
                        type=loc.type,
                        parent=loc.parent,
                        peers=list(loc.peers),
                        role=loc.role,
                        description=loc.description,
                        evidence=loc.evidence,
                    )
                    continue
                for peer in loc.peers:
                    if peer not in existing.peers:
                        existing.peers.append(peer)
                existing.type = existing.type or loc.type
                existing.parent = existing.parent or loc.parent
                existing.role = existing.role or loc.role
                existing.description = existing.description or loc.description
                existing.evidence = existing.evidence or loc.evidence
        merged.locations = list(loc_by_name.values())

        # events: 按 (event_type, title) 去重
        ev_seen: set[tuple[str, str]] = set()
        for f in facts:
            for ev in f.events:
                key = (ev.event_type, ev.title)
                if key in ev_seen:
                    continue
                ev_seen.add(key)
                merged.events.append(ev)

        # item_events: 按 (name, action) 去重
        item_seen: set[tuple[str, str]] = set()
        for f in facts:
            for it in f.item_events:
                key = (it.name, it.action)
                if key in item_seen:
                    continue
                item_seen.add(key)
                merged.item_events.append(it)

        # org_events: 按 (name, action) 去重
        org_seen: set[tuple[str, str]] = set()
        for f in facts:
            for org in f.org_events:
                key = (org.name, org.action)
                if key in org_seen:
                    continue
                org_seen.add(key)
                merged.org_events.append(org)

        # new_concepts: 按 name 去重
        concept_seen: set[str] = set()
        for f in facts:
            for cp in f.new_concepts:
                if cp.name in concept_seen:
                    continue
                concept_seen.add(cp.name)
                merged.new_concepts.append(cp)

        return merged


# ---------------------------------------------------------------------------
# Helpers：JSON dict → dataclass
# ---------------------------------------------------------------------------


def _get_str(d: dict, key: str) -> Optional[str]:
    val = d.get(key)
    return val.strip() if isinstance(val, str) and val.strip() else None


def _get_str_list(d: dict, key: str) -> list[str]:
    val = d.get(key)
    if not isinstance(val, list):
        return []
    return [v.strip() for v in val if isinstance(v, str) and v.strip()]


def _parse_characters(data: Any) -> list[CharacterFact]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = _get_str(item, "name")
        if not name:
            continue
        out.append(CharacterFact(
            name=name,
            new_aliases=_get_str_list(item, "new_aliases"),
            role_hint=_get_str(item, "role_hint"),
            appearance=_get_str(item, "appearance"),
            abilities_gained=_get_str_list(item, "abilities_gained"),
            locations_in_chapter=_get_str_list(item, "locations_in_chapter"),
            evidence=_get_str(item, "evidence"),
        ))
    return out


def _parse_relationships(data: Any) -> list[RelationFact]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        a = _get_str(item, "person_a")
        b = _get_str(item, "person_b")
        rt = _get_str(item, "relation_type")
        if not (a and b and rt):
            continue
        out.append(RelationFact(
            person_a=a, person_b=b, relation_type=rt,
            evidence=_get_str(item, "evidence"),
        ))
    return out


def _parse_locations(data: Any) -> list[LocationFact]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = _get_str(item, "name")
        if not name:
            continue
        out.append(LocationFact(
            name=name,
            type=_get_str(item, "type"),
            parent=_get_str(item, "parent"),
            peers=_get_str_list(item, "peers"),
            role=_get_str(item, "role"),
            description=_get_str(item, "description"),
            evidence=_get_str(item, "evidence"),
        ))
    return out


def _parse_events(data: Any) -> list[EventFact]:
    if not isinstance(data, list):
        return []
    valid_imp = {Importance.HIGH.value, Importance.MEDIUM.value, Importance.LOW.value}
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        et = _get_str(item, "event_type") or "other"
        title = _get_str(item, "title")
        if not title:
            continue
        imp = _get_str(item, "importance") or "medium"
        if imp not in valid_imp:
            imp = "medium"
        out.append(EventFact(
            event_type=et, title=title,
            description=_get_str(item, "description"),
            actors=_get_str_list(item, "actors"),
            location=_get_str(item, "location"),
            importance=imp,
            evidence=_get_str(item, "evidence"),
        ))
    return out


def _parse_items(data: Any) -> list[ItemFact]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = _get_str(item, "name")
        if not name:
            continue
        out.append(ItemFact(
            name=name,
            type=_get_str(item, "type"),
            owner=_get_str(item, "owner"),
            action=_get_str(item, "action") or "mentioned",
            description=_get_str(item, "description"),
            evidence=_get_str(item, "evidence"),
        ))
    return out


def _parse_orgs(data: Any) -> list[OrgFact]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = _get_str(item, "name")
        if not name:
            continue
        out.append(OrgFact(
            name=name,
            action=_get_str(item, "action") or "mentioned",
            description=_get_str(item, "description"),
            members_mentioned=_get_str_list(item, "members_mentioned"),
        ))
    return out


def _parse_concepts(data: Any) -> list[ConceptFact]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = _get_str(item, "name")
        if not name:
            continue
        out.append(ConceptFact(
            name=name,
            type=_get_str(item, "type"),
            description=_get_str(item, "description"),
            evidence=_get_str(item, "evidence"),
        ))
    return out
