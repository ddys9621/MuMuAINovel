"""拆书 V3.1: Verification Pass（聚合后冲突 LLM 仲裁）

触发场景：聚合阶段对以下 3 类字段检测到跨章节冲突时，把候选值与 evidence 送给
LLM 仲裁，结果回写 EntityProfile 并打 verified=true 标记。

支持的冲突字段：
1. role_type：角色叙事定位投票分散（最高占比 < 60% 且至少 3 票）
2. appearance：角色外貌描述出现 ≥ 2 个不同非空值
3. location_type：地点类型出现 ≥ 2 个不同非空值

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §3
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.services.book_dissect.prompts import (
    SYSTEM_PROMPT_V31_VERIFICATION,
    VERIFICATION_PROMPT_V31,
)
from app.services.book_dissect.v2_types import (
    ChapterFact,
    EntityProfile,
    EntityType,
)
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

# role_type 投票最高占比阈值：低于此值视为分散冲突
ROLE_TYPE_DOMINANCE_THRESHOLD = 0.6

# role_type 进入仲裁的最小总票数（避免极少票的实体被误判）
ROLE_TYPE_MIN_VOTES = 3

# appearance 文本相似度阈值：超过则视为同一描述（不冲突）
# 朴素实现：基于公共子串长度比；更复杂的方法不在本期范围
APPEARANCE_SIMILARITY_THRESHOLD = 0.7

# 单本书最大冲突仲裁条数（控制 LLM 输入规模）
MAX_CONFLICTS_PER_CALL = 30

# evidence 文本截断长度
EVIDENCE_TEXT_CAP = 120

# 单字段候选值最多保留多少个（避免长尾噪声）
MAX_CANDIDATES_PER_FIELD = 5

# 支持的字段
SUPPORTED_FIELDS = ("role_type", "appearance", "location_type")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ConflictCandidate:
    """单个候选值（带 evidence）。"""

    value: str
    evidence_chapters: list[int] = field(default_factory=list)
    evidence_texts: list[str] = field(default_factory=list)
    vote_count: int = 0


@dataclass
class EntityConflict:
    """单个实体在某字段上的冲突清单。"""

    canonical_name: str
    field: str  # role_type / appearance / location_type
    candidates: list[ConflictCandidate] = field(default_factory=list)
    appearance_count: int = 0  # 该实体的全书出场次数（排序用）


# ---------------------------------------------------------------------------
# ConflictDetector：从 chapter_facts 重新计算冲突（不依赖 aggregator 内部状态）
# ---------------------------------------------------------------------------


class ConflictDetector:
    """从聚合后的 entities + chapter_facts 中识别字段冲突。"""

    def detect(
        self,
        entities: list[EntityProfile],
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
    ) -> list[EntityConflict]:
        """主入口：识别所有进入仲裁池的冲突。

        Args:
            entities: 已聚合的实体清单
            chapter_facts: 单章 fact（提供 evidence 来源）
            alias_map: 别名 → canonical 映射

        Returns:
            按"appearance_count × candidates 数"倒序的冲突清单，最多 MAX_CONFLICTS_PER_CALL 条
        """
        if not entities or not chapter_facts:
            return []

        person_names = {
            e.canonical_name for e in entities
            if e.entity_type == EntityType.PERSON.value
        }
        location_names = {
            e.canonical_name for e in entities
            if e.entity_type == EntityType.LOCATION.value
        }
        appearance_count_map = {e.canonical_name: e.appearance_count for e in entities}

        # V4.2.3：收集已被 L2 兜底升级为 protagonist 的角色，跳过仲裁保护
        fallback_protected = {
            e.canonical_name for e in entities
            if e.entity_type == EntityType.PERSON.value
            and e.profile_extras.get("_role_type_fallback") is True
            and e.role_type == "protagonist"
        }

        conflicts: list[EntityConflict] = []

        # 1. role_type 冲突（仅 person，且跳过 L2 兜底锁定的）
        conflicts.extend(self._detect_role_type_conflicts(
            chapter_facts, alias_map, person_names, appearance_count_map,
            fallback_protected=fallback_protected,
        ))

        # 2. appearance 冲突（仅 person）
        conflicts.extend(self._detect_appearance_conflicts(
            chapter_facts, alias_map, person_names, appearance_count_map,
        ))

        # 3. location_type 冲突（仅 location）
        conflicts.extend(self._detect_location_type_conflicts(
            chapter_facts, alias_map, location_names, appearance_count_map,
        ))

        # 排序：按重要性倒序（出场多的实体冲突优先）
        conflicts.sort(
            key=lambda c: (-c.appearance_count, -len(c.candidates)),
        )
        return conflicts[:MAX_CONFLICTS_PER_CALL]

    # ------------------------------------------------------------------
    # 内部：各字段冲突检测
    # ------------------------------------------------------------------

    def _detect_role_type_conflicts(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
        person_names: set[str],
        appearance_count_map: dict[str, int],
        fallback_protected: set[str] | None = None,
    ) -> list[EntityConflict]:
        """role_type 投票分散即冲突。

        Args:
            fallback_protected: V4.2.3 — 已被 L2 兜底升级为 protagonist 的角色名集合，
                这些角色的 role_type 已被锁定，跳过仲裁池避免 LLM 推翻。
        """
        fallback_protected = fallback_protected or set()
        # canonical -> Counter[role_hint -> 票数]
        votes: dict[str, Counter] = defaultdict(Counter)
        # canonical -> role_hint -> {chapter_numbers, evidence_texts}
        evidence: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
            lambda: {"chapters": [], "texts": []}
        ))

        for fact in chapter_facts:
            for cf in fact.characters:
                canon = alias_map.get(cf.name, cf.name)
                if canon not in person_names:
                    continue
                if not cf.role_hint:
                    continue
                votes[canon][cf.role_hint] += 1
                ev = evidence[canon][cf.role_hint]
                if fact.chapter_number not in ev["chapters"]:
                    ev["chapters"].append(fact.chapter_number)
                if cf.evidence and len(ev["texts"]) < 3:
                    ev["texts"].append(_truncate(cf.evidence, EVIDENCE_TEXT_CAP))

        out: list[EntityConflict] = []
        for canon, ctr in votes.items():
            # V4.2.3 兜底保护：已被 L2 升级为 protagonist 的角色，
            # role_type 已锁定，跳过仲裁池（即便投票分散也不进入）
            if canon in fallback_protected:
                logger.debug(
                    "[ConflictDetector] '%s' 已被 L2 兜底升级 protagonist，跳过 role_type 仲裁",
                    canon,
                )
                continue
            total = sum(ctr.values())
            if total < ROLE_TYPE_MIN_VOTES:
                continue
            top_count = ctr.most_common(1)[0][1]
            if top_count / total >= ROLE_TYPE_DOMINANCE_THRESHOLD:
                continue
            # 进入冲突池
            cands = []
            for hint, cnt in ctr.most_common(MAX_CANDIDATES_PER_FIELD):
                ev = evidence[canon][hint]
                cands.append(ConflictCandidate(
                    value=hint,
                    evidence_chapters=list(ev["chapters"]),
                    evidence_texts=list(ev["texts"]),
                    vote_count=cnt,
                ))
            out.append(EntityConflict(
                canonical_name=canon,
                field="role_type",
                candidates=cands,
                appearance_count=appearance_count_map.get(canon, 0),
            ))
        return out

    def _detect_appearance_conflicts(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
        person_names: set[str],
        appearance_count_map: dict[str, int],
    ) -> list[EntityConflict]:
        """appearance 出现 ≥2 个不同非空描述视为冲突。"""
        # canonical -> list[(value, chapter_number, evidence)]
        records: dict[str, list[tuple[str, int, Optional[str]]]] = defaultdict(list)

        for fact in chapter_facts:
            for cf in fact.characters:
                canon = alias_map.get(cf.name, cf.name)
                if canon not in person_names:
                    continue
                if not cf.appearance:
                    continue
                appearance = cf.appearance.strip()
                if not appearance:
                    continue
                records[canon].append(
                    (appearance, fact.chapter_number, cf.evidence)
                )

        out: list[EntityConflict] = []
        for canon, items in records.items():
            buckets = self._bucket_similar(items)
            if len(buckets) < 2:
                continue
            # 每个 bucket 一个候选
            cands = []
            for bucket in buckets[:MAX_CANDIDATES_PER_FIELD]:
                # 取章节号最大的描述作为 bucket 代表（最新版本）
                bucket_sorted = sorted(bucket, key=lambda r: -r[1])
                rep_value = bucket_sorted[0][0]
                chapters = sorted({r[1] for r in bucket})
                texts = [
                    _truncate(r[2], EVIDENCE_TEXT_CAP)
                    for r in bucket if r[2]
                ][:3]
                cands.append(ConflictCandidate(
                    value=rep_value,
                    evidence_chapters=chapters,
                    evidence_texts=texts,
                    vote_count=len(bucket),
                ))
            out.append(EntityConflict(
                canonical_name=canon,
                field="appearance",
                candidates=cands,
                appearance_count=appearance_count_map.get(canon, 0),
            ))
        return out

    def _detect_location_type_conflicts(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
        location_names: set[str],
        appearance_count_map: dict[str, int],
    ) -> list[EntityConflict]:
        """location.type 出现 ≥2 个不同非空值视为冲突。"""
        records: dict[str, list[tuple[str, int, Optional[str]]]] = defaultdict(list)

        for fact in chapter_facts:
            for loc in fact.locations:
                canon = alias_map.get(loc.name, loc.name)
                if canon not in location_names:
                    continue
                if not loc.type:
                    continue
                t = loc.type.strip()
                if not t:
                    continue
                records[canon].append((t, fact.chapter_number, loc.evidence))

        out: list[EntityConflict] = []
        for canon, items in records.items():
            type_counter = Counter(r[0] for r in items)
            distinct_types = list(type_counter.keys())
            if len(distinct_types) < 2:
                continue

            cands = []
            for t, cnt in type_counter.most_common(MAX_CANDIDATES_PER_FIELD):
                bucket = [r for r in items if r[0] == t]
                chapters = sorted({r[1] for r in bucket})
                texts = [
                    _truncate(r[2], EVIDENCE_TEXT_CAP)
                    for r in bucket if r[2]
                ][:3]
                cands.append(ConflictCandidate(
                    value=t,
                    evidence_chapters=chapters,
                    evidence_texts=texts,
                    vote_count=cnt,
                ))
            out.append(EntityConflict(
                canonical_name=canon,
                field="location_type",
                candidates=cands,
                appearance_count=appearance_count_map.get(canon, 0),
            ))
        return out

    # ------------------------------------------------------------------
    # 工具：appearance 文本相似度分桶
    # ------------------------------------------------------------------

    def _bucket_similar(
        self,
        items: list[tuple[str, int, Optional[str]]],
    ) -> list[list[tuple[str, int, Optional[str]]]]:
        """把相似度高的 appearance 描述合并到同一 bucket。

        实现：朴素贪心。两两比较，相似度 >= APPEARANCE_SIMILARITY_THRESHOLD 视为同 bucket。
        """
        if not items:
            return []
        buckets: list[list[tuple[str, int, Optional[str]]]] = []
        for it in items:
            placed = False
            for b in buckets:
                if _string_similar(it[0], b[0][0]) >= APPEARANCE_SIMILARITY_THRESHOLD:
                    b.append(it)
                    placed = True
                    break
            if not placed:
                buckets.append([it])
        # 按 bucket 大小倒序（出现次数多的优先）
        buckets.sort(key=lambda b: -len(b))
        return buckets


# ---------------------------------------------------------------------------
# VerificationPass：调一次 LLM 做仲裁
# ---------------------------------------------------------------------------


class VerificationPass:
    """聚合后冲突 LLM 仲裁。"""

    DEFAULT_TEMPERATURE = 0.1
    MAX_TOKENS = 3000

    def __init__(self, ai_service):
        """
        Args:
            ai_service: app.services.ai_service.AIService 实例
        """
        self.ai_service = ai_service

    async def resolve(
        self,
        conflicts: list[EntityConflict],
    ) -> dict[tuple[str, str], Optional[str]]:
        """对 conflicts 调一次 LLM 仲裁。

        Returns:
            { (canonical_name, field): final_value }
            final_value 可能为 None（LLM 拿不准）
            未在返回中的 (name, field) 表示 LLM 漏给，调用方应保留静态合并结果
        """
        if not conflicts:
            return {}

        # 截断到上限
        sliced = conflicts[:MAX_CONFLICTS_PER_CALL]
        user_prompt = self._build_user_prompt(sliced)

        try:
            resp = await self.ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT_V31_VERIFICATION,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as exc:
            logger.error("[拆书V3.1-仲裁] LLM 调用失败: %s", exc)
            return {}

        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[拆书V3.1-仲裁] LLM 返回空内容")
            return {}

        return self._parse_response(content, sliced)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build_user_prompt(self, conflicts: list[EntityConflict]) -> str:
        payload = []
        for c in conflicts:
            payload.append({
                "canonical_name": c.canonical_name,
                "field": c.field,
                "appearance_count": c.appearance_count,
                "candidates": [
                    {
                        "value": cand.value,
                        "vote_count": cand.vote_count,
                        "evidence_chapters": cand.evidence_chapters,
                        "evidence_texts": cand.evidence_texts,
                    }
                    for cand in c.candidates
                ],
            })
        conflicts_json = json.dumps(payload, ensure_ascii=False, indent=2)
        return VERIFICATION_PROMPT_V31.format(conflicts=conflicts_json)

    def _parse_response(
        self,
        raw_text: str,
        conflicts: list[EntityConflict],
    ) -> dict[tuple[str, str], Optional[str]]:
        """解析 LLM 输出 JSON → resolutions dict。"""
        result = safe_parse_json(
            raw_text,
            default=None,
            expected_type="object",
            log_prefix="[拆书V3.1-仲裁]",
        )
        if not isinstance(result, dict):
            logger.warning("[拆书V3.1-仲裁] JSON 解析后非 object")
            return {}

        # 索引：合法的 (name, field) 组合，用于过滤 LLM 凭空生成的条目
        valid_pairs = {(c.canonical_name, c.field) for c in conflicts}
        # 索引：合法的候选值集合，用于过滤 LLM 自创值
        valid_values: dict[tuple[str, str], set[str]] = {
            (c.canonical_name, c.field): {cand.value for cand in c.candidates}
            for c in conflicts
        }

        out: dict[tuple[str, str], Optional[str]] = {}
        items = result.get("resolutions") or []
        if not isinstance(items, list):
            logger.warning("[拆书V3.1-仲裁] resolutions 字段非 list")
            return {}

        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("canonical_name")
            field = item.get("field")
            final = item.get("final_value")
            if not isinstance(name, str) or not isinstance(field, str):
                continue
            name = name.strip()
            field = field.strip()
            if (name, field) not in valid_pairs:
                continue
            if final is None:
                out[(name, field)] = None
                continue
            if not isinstance(final, str):
                continue
            final = final.strip()
            if not final:
                out[(name, field)] = None
                continue
            # 严格模式：LLM 给出的 final_value 必须在候选集中
            # （防止 LLM 自创新值；如果用户希望宽松，可改为 warning + 接受）
            if final not in valid_values.get((name, field), set()):
                logger.warning(
                    "[拆书V3.1-仲裁] LLM 自创值被忽略 name=%s field=%s value=%r",
                    name, field, final,
                )
                continue
            out[(name, field)] = final

        return out


# ---------------------------------------------------------------------------
# apply_resolutions：把仲裁结果回写 EntityProfile
# ---------------------------------------------------------------------------


def apply_resolutions(
    entities: list[EntityProfile],
    resolutions: dict[tuple[str, str], Optional[str]],
) -> list[EntityProfile]:
    """把 LLM 仲裁结果回写到 EntityProfile，并打 verified 标记。

    final_value=None 表示 LLM 拿不准，保留静态合并结果，但仍记录 verified=true（已经过仲裁）。

    F4-extension：role_type 字段仲裁前后记录 INFO 审计日志，
    便于追踪反英雄 / 视角主导场景的判定过程与最终结果。

    Returns:
        同一个 entities list（原地修改后返回，便于链式调用）
    """
    if not resolutions:
        return entities
    by_name: dict[str, EntityProfile] = {e.canonical_name: e for e in entities}
    for (name, field), final_value in resolutions.items():
        e = by_name.get(name)
        if e is None:
            continue
        if final_value is not None:
            if field == "role_type":
                # V4.2.3 双保险：即便 ConflictDetector 漏拦（不应该），
                # 已被 L2 升级为 protagonist 的角色也不允许被推翻
                if (
                    e.profile_extras.get("_role_type_fallback") is True
                    and e.role_type == "protagonist"
                    and final_value != "protagonist"
                ):
                    logger.info(
                        "[apply_resolutions] LLM 仲裁 '%s' → %s 被拦截，"
                        "保持 L2 兜底 protagonist 不变",
                        name, final_value,
                    )
                    continue
                # F4-extension 审计日志：记录 role_type 实际改动
                old_role = e.role_type
                if old_role != final_value:
                    logger.info(
                        "[apply_resolutions] role_type 仲裁通过 '%s': %s → %s "
                        "(appearance_count=%d)",
                        name, old_role, final_value, e.appearance_count,
                    )
                e.role_type = final_value
            elif field == "appearance":
                e.profile_extras["appearance"] = final_value
            elif field == "location_type":
                e.profile_extras["type"] = final_value
            else:
                # 未知字段，跳过
                continue
        elif field == "role_type":
            # final_value=None 但是 role_type 字段：LLM 拿不准
            logger.info(
                "[apply_resolutions] role_type 仲裁未决 '%s' (current=%s)，"
                "保留静态合并结果",
                name, e.role_type,
            )
        # 即使 final_value=None 也记 verified（已仲裁过）
        verified_fields = e.profile_extras.setdefault("verified_fields", [])
        if field not in verified_fields:
            verified_fields.append(field)
        e.profile_extras["verified"] = True
    return entities


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _truncate(text: Optional[str], cap: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= cap:
        return text
    return text[: cap - 1] + "…"


def _string_similar(a: str, b: str) -> float:
    """朴素相似度：基于公共字符集 Jaccard。

    用于 appearance 描述聚类，不需要很精确。
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    set_a = set(a)
    set_b = set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return inter / union
