"""拆书 V2: 全书实体聚合器（Phase 5）

输入：
- alias_map: dict[name -> canonical_name]（来自 AliasResolver）
- chapter_facts: list[ChapterFact]（已经过 FactValidator）
- dictionary: list[DictionaryEntry]（提供 entity_type）

输出：list[EntityProfile]（按 canonical_name 聚合的全书实体档案）

聚合维度（仅 person）：
- canonical_name / aliases
- entity_type（来自字典）
- first_chapter / last_chapter / appearance_count
- role_type（投票：所有 ChapterFact.characters[].role_hint 投票，多数胜）
- profile_extras：abilities / locations / appearance（多章合并）

F4 兜底（2026-05-21 V4.2.3）：
- 投票结束后如果所有 person 都没有被标为 protagonist，按 appearance_count
  取出场最多的 person 强制升级为 protagonist
- 触发场景：短篇 / 单章 / LLM 把主角标成 antagonist（如「秤魂」女反派当主角）
- 标记 profile_extras["_role_type_fallback"]=True 让上层能区分
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

from app.services.book_dissect.v2_types import (
    ChapterFact,
    DictionaryEntry,
    EntityProfile,
    EntityType,
)

logger = logging.getLogger(__name__)


class EntityAggregator:
    """全书实体档案聚合。"""

    def aggregate(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
        dictionary: list[DictionaryEntry],
    ) -> list[EntityProfile]:
        """主入口：按 canonical_name 聚合实体。"""
        # 字典 lookup：name → entity_type
        type_by_name: dict[str, str] = {}
        for entry in dictionary:
            if entry.entity_type in ("rejected", "unknown"):
                continue
            type_by_name[entry.name] = entry.entity_type

        # 聚合容器
        profiles: dict[str, EntityProfile] = {}

        # ----------- 1. 角色（来自 ChapterFact.characters） -----------
        for fact in chapter_facts:
            for cf in fact.characters:
                canon = alias_map.get(cf.name, cf.name)
                if not canon:
                    continue
                profile = profiles.get(canon)
                if profile is None:
                    profile = EntityProfile(
                        canonical_name=canon,
                        entity_type=type_by_name.get(canon, EntityType.PERSON.value),
                        aliases=[],
                        first_chapter=fact.chapter_number,
                        last_chapter=fact.chapter_number,
                        appearance_count=0,
                        role_type=None,
                        profile_extras={
                            "abilities": [],
                            "locations": [],
                            "appearance": None,
                            "evidence_chapters": [],
                            "_role_votes": Counter(),
                        },
                    )
                    profiles[canon] = profile

                profile.appearance_count += 1
                profile.last_chapter = max(profile.last_chapter or 0, fact.chapter_number)
                profile.first_chapter = min(
                    profile.first_chapter if profile.first_chapter is not None else fact.chapter_number,
                    fact.chapter_number,
                )

                # 别名累加
                for alias in cf.new_aliases:
                    alias_canon = alias_map.get(alias, alias)
                    if alias_canon == canon and alias != canon and alias not in profile.aliases:
                        profile.aliases.append(alias)
                # 别名也吸收 cf.name 自身（如果它不是 canonical）
                if cf.name != canon and cf.name not in profile.aliases:
                    profile.aliases.append(cf.name)

                # role_type 投票
                if cf.role_hint:
                    profile.profile_extras["_role_votes"][cf.role_hint] += 1

                # abilities 合并
                for ab in cf.abilities_gained:
                    if ab not in profile.profile_extras["abilities"]:
                        profile.profile_extras["abilities"].append(ab)
                # locations 合并
                for loc in cf.locations_in_chapter:
                    if loc not in profile.profile_extras["locations"]:
                        profile.profile_extras["locations"].append(loc)
                # appearance：取首个非空
                if cf.appearance and not profile.profile_extras["appearance"]:
                    profile.profile_extras["appearance"] = cf.appearance
                # 出场章节
                if fact.chapter_number not in profile.profile_extras["evidence_chapters"]:
                    profile.profile_extras["evidence_chapters"].append(fact.chapter_number)

        # ----------- 2. 地点（来自 ChapterFact.locations） -----------
        for fact in chapter_facts:
            for loc in fact.locations:
                canon = alias_map.get(loc.name, loc.name)
                if not canon:
                    continue
                profile = profiles.get(canon)
                if profile is None:
                    profile = EntityProfile(
                        canonical_name=canon,
                        entity_type=type_by_name.get(canon, EntityType.LOCATION.value),
                        aliases=[],
                        first_chapter=fact.chapter_number,
                        last_chapter=fact.chapter_number,
                        appearance_count=0,
                        role_type=None,
                        profile_extras={
                            "type": loc.type,
                            "parent": loc.parent,
                            "peers": list(loc.peers),
                            "description": loc.description,
                            "evidence_chapters": [],
                        },
                    )
                    profiles[canon] = profile
                # 已存在
                profile.appearance_count += 1
                profile.last_chapter = max(profile.last_chapter or 0, fact.chapter_number)
                profile.first_chapter = min(
                    profile.first_chapter if profile.first_chapter is not None else fact.chapter_number,
                    fact.chapter_number,
                )
                if fact.chapter_number not in profile.profile_extras.get("evidence_chapters", []):
                    profile.profile_extras.setdefault("evidence_chapters", []).append(fact.chapter_number)
                # 类型 / 描述补全
                if loc.type and not profile.profile_extras.get("type"):
                    profile.profile_extras["type"] = loc.type
                if loc.parent and not profile.profile_extras.get("parent"):
                    profile.profile_extras["parent"] = loc.parent
                if loc.description and not profile.profile_extras.get("description"):
                    profile.profile_extras["description"] = loc.description
                for peer in loc.peers:
                    if peer not in profile.profile_extras.setdefault("peers", []):
                        profile.profile_extras["peers"].append(peer)

        # ----------- 3. 选择 role_type（投票） -----------
        for profile in profiles.values():
            votes = profile.profile_extras.pop("_role_votes", None)
            if isinstance(votes, Counter) and votes:
                # 取得票最高的 role_hint
                profile.role_type = votes.most_common(1)[0][0]

        # ----------- 3.5. F4 protagonist 兜底（V4.2.3 修复）-----------
        # 触发：LLM 未标 protagonist / 全部标为 antagonist|supporting|minor
        # 策略：按 appearance_count 取出场最多 person 升级为 protagonist
        _apply_protagonist_fallback(profiles)

        # ----------- 4. 排序 -----------
        result = list(profiles.values())
        result.sort(
            key=lambda p: (
                # person > location > org > item > concept
                _entity_type_priority(p.entity_type),
                -p.appearance_count,
                p.first_chapter or 99999,
            )
        )
        return result


def _entity_type_priority(t: str) -> int:
    order = {
        EntityType.PERSON.value: 0,
        EntityType.LOCATION.value: 1,
        EntityType.ORG.value: 2,
        EntityType.ITEM.value: 3,
        EntityType.CONCEPT.value: 4,
    }
    return order.get(t, 99)


def _apply_protagonist_fallback(profiles: dict[str, EntityProfile]) -> None:
    """F4 兜底：当所有 person 都没有被标为 protagonist 时，按出场次数兜底。

    触发条件：所有 entity_type=person 的 profile 中无任何 role_type=protagonist
    策略：
        1. 优先选 appearance_count 最高的 person
        2. 平票时，选 first_chapter 最早的（最早出场 = 视角中心可能性大）
        3. 仍平票时，选 canonical_name 字典序最小（保证确定性）
    标记：被升级的 profile.profile_extras["_role_type_fallback"]=True

    特殊处理：
    - 把原 role_type 保留在 profile_extras["_role_type_original"] 便于审计
    - 如果原本是 antagonist（如「秤魂」杨令珊），日志 INFO 级别提示
    - 如果原本是 None 或 minor，日志 DEBUG 级别（属于正常兜底）
    """
    person_profiles = [
        p for p in profiles.values()
        if p.entity_type == EntityType.PERSON.value
    ]
    if not person_profiles:
        return  # 没 person 实体，无需兜底

    has_protagonist = any(p.role_type == "protagonist" for p in person_profiles)
    if has_protagonist:
        return  # 已经有 protagonist，不兜底

    # 按 (appearance_count desc, first_chapter asc, canonical_name asc) 选 top-1
    top = max(
        person_profiles,
        key=lambda p: (
            p.appearance_count or 0,
            -(p.first_chapter or 99999),  # 负号让 min first_chapter 排前
            # 字典序倒序：因 max + 元组，最后一项也要倒，但字符串无法直接负号
            # 用反向比较：先按前两项 max，最后用 sorted 二级兜底
        ),
    )
    # canonical_name 平票兜底（极少触发）
    candidates = [
        p for p in person_profiles
        if (p.appearance_count or 0) == (top.appearance_count or 0)
        and (p.first_chapter or 99999) == (top.first_chapter or 99999)
    ]
    if len(candidates) > 1:
        top = min(candidates, key=lambda p: p.canonical_name or "")

    original = top.role_type
    top.role_type = "protagonist"
    top.profile_extras["_role_type_fallback"] = True
    top.profile_extras["_role_type_original"] = original

    if original == "antagonist":
        # 用户故事可能是"反派当主角"，明确提示
        logger.info(
            "[EntityAggregator F4 兜底] '%s' 原 role_hint=antagonist → 升级为 protagonist "
            "（出场=%d，首章=%s）。可能是反英雄故事，请人工核验",
            top.canonical_name, top.appearance_count or 0, top.first_chapter,
        )
    else:
        logger.warning(
            "[EntityAggregator F4 兜底] 无 protagonist，按出场次数选 '%s' "
            "（原 role_type=%s，出场=%d，首章=%s）",
            top.canonical_name, original, top.appearance_count or 0, top.first_chapter,
        )
