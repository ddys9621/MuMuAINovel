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
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from app.services.book_dissect.v2_types import (
    ChapterFact,
    DictionaryEntry,
    EntityProfile,
    EntityType,
)


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
