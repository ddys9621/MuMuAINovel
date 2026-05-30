"""F4 修复测试：role_type protagonist 三层兜底 + verification 保护机制。

覆盖：
- L2 EntityAggregator._apply_protagonist_fallback（11 个测试）
- L3 CharacterArchiveBuilder 双保险（4 个测试）
- E2E L2+L3 双层兜底联动（2 个测试）
- L4 verification_pass 保护（V4.2.3 新增）：
  - ConflictDetector 跳过 L2 兜底锁定的角色
  - apply_resolutions 双保险拦截 LLM 推翻 protagonist 兜底
- L5 character_archive _inferred 标记透传（V4.2.3 新增）：
  - L2 兜底的 protagonist 序列化时带 _inferred=True
  - L3 双保险的 protagonist 序列化时带 _inferred=True
  - 正常 protagonist 不带 _inferred
"""
from __future__ import annotations

from collections import Counter

import pytest

from app.services.book_dissect.character_archive_builder import (
    CharacterArchiveBuilder,
)
from app.services.book_dissect.entity_aggregator import (
    _apply_protagonist_fallback,
)
from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    EntityProfile,
    EntityType,
)
from app.services.book_dissect.verification_pass import (
    ConflictDetector,
    apply_resolutions,
)


# ============================================================
# helpers
# ============================================================


def make_person(
    name: str,
    *,
    appearance_count: int = 1,
    first_chapter: int | None = 1,
    last_chapter: int | None = 1,
    role_type: str | None = None,
) -> EntityProfile:
    return EntityProfile(
        canonical_name=name,
        entity_type=EntityType.PERSON.value,
        appearance_count=appearance_count,
        first_chapter=first_chapter,
        last_chapter=last_chapter,
        role_type=role_type,
        profile_extras={},
    )


def make_location(name: str) -> EntityProfile:
    return EntityProfile(
        canonical_name=name,
        entity_type=EntityType.LOCATION.value,
        appearance_count=1,
        first_chapter=1,
    )


def to_dict(profiles: list[EntityProfile]) -> dict[str, EntityProfile]:
    return {p.canonical_name: p for p in profiles}


# ============================================================
# L2: EntityAggregator._apply_protagonist_fallback
# ============================================================


class TestL2EntityAggregatorFallback:
    """L2 EntityAggregator 兜底测试。"""

    def test_has_protagonist_no_fallback(self):
        """已有 protagonist → 不触发兜底，不修改任何 profile。"""
        profiles = to_dict([
            make_person("主角", appearance_count=10, role_type="protagonist"),
            make_person("反派", appearance_count=5, role_type="antagonist"),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["主角"].role_type == "protagonist"
        assert profiles["反派"].role_type == "antagonist"
        assert "_role_type_fallback" not in profiles["主角"].profile_extras
        assert "_role_type_fallback" not in profiles["反派"].profile_extras

    def test_all_antagonist_fallback_promotes_top_appearance(self):
        """全部 antagonist → 出场最多的升级为 protagonist（秤魂女反派场景）。"""
        profiles = to_dict([
            make_person("杨令珊", appearance_count=10, role_type="antagonist"),
            make_person("国师", appearance_count=3, role_type="antagonist"),
            make_person("仁宗", appearance_count=2, role_type="antagonist"),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["杨令珊"].role_type == "protagonist"
        assert profiles["杨令珊"].profile_extras["_role_type_fallback"] is True
        assert profiles["杨令珊"].profile_extras["_role_type_original"] == "antagonist"
        assert profiles["国师"].role_type == "antagonist"  # 未被改
        assert profiles["仁宗"].role_type == "antagonist"

    def test_all_supporting_fallback(self):
        """全部 supporting → 兜底升级。"""
        profiles = to_dict([
            make_person("A", appearance_count=5, role_type="supporting"),
            make_person("B", appearance_count=8, role_type="supporting"),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["B"].role_type == "protagonist"
        assert profiles["B"].profile_extras["_role_type_original"] == "supporting"
        assert profiles["A"].role_type == "supporting"

    def test_all_none_fallback(self):
        """全部 None → 兜底升级。"""
        profiles = to_dict([
            make_person("张三", appearance_count=3),  # role_type=None
            make_person("李四", appearance_count=5),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["李四"].role_type == "protagonist"
        assert profiles["李四"].profile_extras["_role_type_original"] is None

    def test_all_minor_fallback(self):
        """全部 minor → 兜底升级。"""
        profiles = to_dict([
            make_person("A", appearance_count=2, role_type="minor"),
            make_person("B", appearance_count=4, role_type="minor"),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["B"].role_type == "protagonist"

    def test_tie_appearance_first_chapter_wins(self):
        """appearance 相同 → first_chapter 早的赢。"""
        profiles = to_dict([
            make_person("早出场", appearance_count=5, first_chapter=1, role_type="supporting"),
            make_person("晚出场", appearance_count=5, first_chapter=10, role_type="supporting"),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["早出场"].role_type == "protagonist"
        assert profiles["晚出场"].role_type == "supporting"

    def test_tie_appearance_and_first_chapter_canonical_name_wins(self):
        """appearance + first_chapter 都相同 → canonical_name 字典序小的赢。"""
        profiles = to_dict([
            make_person("乙", appearance_count=5, first_chapter=1, role_type="supporting"),
            make_person("甲", appearance_count=5, first_chapter=1, role_type="supporting"),
            make_person("丙", appearance_count=5, first_chapter=1, role_type="supporting"),
        ])
        _apply_protagonist_fallback(profiles)
        # 字典序：丙 < 乙 < 甲（按 Unicode 比较中文）
        # 实际上是 "丙"=0x4e19 "乙"=0x4e59 "甲"=0x7532
        # 所以 "丙" 最小
        assert profiles["丙"].role_type == "protagonist"

    def test_no_person_entities_no_op(self):
        """无 person 实体 → 不操作。"""
        profiles = to_dict([
            make_location("北京"),
            make_location("上海"),
        ])
        _apply_protagonist_fallback(profiles)
        for p in profiles.values():
            assert "_role_type_fallback" not in p.profile_extras

    def test_only_one_person_gets_promoted(self):
        """只有 1 个 person + 无 role_type → 直接兜底升级。"""
        profiles = to_dict([
            make_person("独苗", appearance_count=1),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["独苗"].role_type == "protagonist"
        assert profiles["独苗"].profile_extras["_role_type_fallback"] is True

    def test_mixed_persons_and_locations(self):
        """有 person 也有 location → 仅看 person 投票。"""
        profiles = to_dict([
            make_location("地点1"),
            make_person("主角", appearance_count=5, role_type="supporting"),
            make_location("地点2"),
        ])
        _apply_protagonist_fallback(profiles)
        assert profiles["主角"].role_type == "protagonist"
        # 地点不应被改
        assert profiles["地点1"].role_type is None
        assert profiles["地点2"].role_type is None

    def test_first_chapter_none_not_promoted_over_explicit(self):
        """first_chapter=None 的 person 不应优先于有 first_chapter 的同 appearance person。"""
        profiles = to_dict([
            make_person("无章号", appearance_count=5, first_chapter=None, role_type="supporting"),
            make_person("有章号", appearance_count=5, first_chapter=2, role_type="supporting"),
        ])
        _apply_protagonist_fallback(profiles)
        # 有章号的应该被选中（first_chapter=2 < 99999）
        assert profiles["有章号"].role_type == "protagonist"


# ============================================================
# L3: CharacterArchiveBuilder 双保险
# ============================================================


class TestL3CharacterArchiveBuilderFallback:
    """L3 CharacterArchiveBuilder 双保险测试。

    L3 的作用：即便 L2 没生效（旧数据 / mock 场景），CharacterArchive 自己也能兜底。
    """

    def test_no_protagonist_fallback_to_top_appearance(self):
        """L2 没改 role_type，L3 也能按 appearance 兜底选主角。"""
        builder = CharacterArchiveBuilder()
        persons = [
            make_person("A", appearance_count=3, role_type="supporting"),
            make_person("B", appearance_count=10, role_type="antagonist"),
            make_person("C", appearance_count=5, role_type="supporting"),
        ]
        result = builder.build(entities=persons, total_chapters=1)
        assert len(result["protagonist_archetypes"]) == 1
        assert result["protagonist_archetypes"][0]["name"] == "B"

    def test_protagonist_promoted_removed_from_antagonist_list(self):
        """被升级为 protagonist 的 person 不应出现在 antagonist_progression 中。"""
        builder = CharacterArchiveBuilder()
        # B 原本是 antagonist 但 L3 会因无 protagonist 把它升级
        persons = [
            make_person("A", appearance_count=3, role_type="antagonist"),
            make_person("B", appearance_count=10, role_type="antagonist"),
        ]
        result = builder.build(entities=persons, total_chapters=1)
        # B 升级为 protagonist
        assert result["protagonist_archetypes"][0]["name"] == "B"
        # antagonist_progression 中不应再有 B
        antagonist_names = [a["name"] for a in result["antagonist_progression"]]
        assert "B" not in antagonist_names
        assert "A" in antagonist_names

    def test_has_protagonist_no_double_fallback(self):
        """已有 protagonist → L3 不重复兜底。"""
        builder = CharacterArchiveBuilder()
        persons = [
            make_person("主角", appearance_count=10, role_type="protagonist"),
            make_person("反派", appearance_count=5, role_type="antagonist"),
        ]
        result = builder.build(entities=persons, total_chapters=1)
        assert len(result["protagonist_archetypes"]) == 1
        assert result["protagonist_archetypes"][0]["name"] == "主角"
        assert result["antagonist_progression"][0]["name"] == "反派"

    def test_no_persons_returns_empty(self):
        """无 person 实体 → 返回 empty_result（保持原行为）。"""
        builder = CharacterArchiveBuilder()
        result = builder.build(entities=[make_location("北京")], total_chapters=1)
        assert result == {
            "protagonist_archetypes": [],
            "antagonist_progression": [],
            "support_character_techniques": [],
        }


# ============================================================
# 端到端：L2 + L3 双层兜底联动
# ============================================================


class TestE2EDoubleLayerFallback:
    """L2 + L3 双层兜底联动测试。"""

    def test_l2_fallback_triggers_then_l3_no_op(self):
        """L2 已兜底 → L3 不需要再兜底（避免重复升级）。"""
        # 模拟 L2 已经把"杨令珊"升级为 protagonist
        from app.services.book_dissect.entity_aggregator import (
            _apply_protagonist_fallback,
        )
        profiles = to_dict([
            make_person("杨令珊", appearance_count=10, role_type="antagonist"),
            make_person("国师", appearance_count=3, role_type="antagonist"),
        ])
        _apply_protagonist_fallback(profiles)
        # 此时 杨令珊.role_type = "protagonist"

        # L3 应该正常使用 L2 的结果
        builder = CharacterArchiveBuilder()
        result = builder.build(entities=list(profiles.values()), total_chapters=1)
        assert result["protagonist_archetypes"][0]["name"] == "杨令珊"
        # 国师还是 antagonist
        assert any(a["name"] == "国师" for a in result["antagonist_progression"])

    def test_l2_skipped_l3_kicks_in(self):
        """模拟旧数据（未经 L2 处理）→ L3 能独立兜底。"""
        # 完全 bypass L2，直接给 CharacterArchive 全 antagonist
        builder = CharacterArchiveBuilder()
        persons = [
            make_person("杨令珊", appearance_count=10, role_type="antagonist"),
            make_person("国师", appearance_count=3, role_type="antagonist"),
        ]
        result = builder.build(entities=persons, total_chapters=1)
        # L3 双保险触发
        assert result["protagonist_archetypes"][0]["name"] == "杨令珊"
        # antagonist_progression 应该只有国师（杨令珊被升级移除）
        antagonist_names = [a["name"] for a in result["antagonist_progression"]]
        assert antagonist_names == ["国师"]


# ============================================================
# L4: verification_pass 保护 L2 兜底
# ============================================================


class TestL4VerificationProtection:
    """V4.2.3 — verification_pass 不能推翻 L2 兜底升级的 protagonist。"""

    def test_conflict_detector_skips_fallback_protected(self):
        """ConflictDetector 跳过已被 L2 兜底升级为 protagonist 的角色。

        场景：投票本来是 2 票 antagonist + 2 票 supporting + 1 票 minor（分散）
              本应进入仲裁池，但因为已被 L2 兜底升级，跳过保护
        """
        # 模拟 L2 兜底后的 entity
        proto = make_person(
            "杨令珊",
            appearance_count=5,
            role_type="protagonist",  # 已兜底升级
        )
        proto.profile_extras["_role_type_fallback"] = True
        proto.profile_extras["_role_type_original"] = "antagonist"

        # 构造投票分散的 chapter_facts
        facts = [
            ChapterFact(
                chapter_number=ch,
                characters=[CharacterFact(name="杨令珊", role_hint=hint)],
            )
            for ch, hint in [
                (1, "antagonist"),
                (2, "antagonist"),
                (3, "supporting"),
                (4, "supporting"),
                (5, "minor"),
            ]
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([proto], facts, {"杨令珊": "杨令珊"})
        # 杨令珊不应出现在冲突池（已被 L2 锁定）
        assert all(c.canonical_name != "杨令珊" for c in conflicts)

    def test_conflict_detector_normal_path_still_works(self):
        """非兜底角色的 role_type 仲裁正常工作（不受保护影响）。"""
        normal = make_person("普通角色", appearance_count=5, role_type="supporting")
        # 注意：不加 _role_type_fallback
        facts = [
            ChapterFact(
                chapter_number=ch,
                characters=[CharacterFact(name="普通角色", role_hint=hint)],
            )
            for ch, hint in [
                (1, "supporting"),
                (2, "antagonist"),
                (3, "minor"),
                (4, "supporting"),
                (5, "antagonist"),
            ]
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([normal], facts, {"普通角色": "普通角色"})
        # 投票分散（supporting 2/5 = 40% < 60% 阈值）→ 应进入冲突池
        assert len(conflicts) == 1
        assert conflicts[0].canonical_name == "普通角色"

    def test_apply_resolutions_blocks_protagonist_override(self):
        """apply_resolutions 双保险：即便 LLM 给出非-protagonist 结果，也不能推翻 L2 兜底。"""
        proto = make_person(
            "杨令珊",
            appearance_count=5,
            role_type="protagonist",
        )
        proto.profile_extras["_role_type_fallback"] = True
        proto.profile_extras["_role_type_original"] = "antagonist"

        # 模拟 LLM 仲裁结果：把 杨令珊 改回 antagonist
        resolutions = {("杨令珊", "role_type"): "antagonist"}

        result = apply_resolutions([proto], resolutions)
        # 双保险拦截：role_type 仍是 protagonist
        assert result[0].role_type == "protagonist"
        # fallback 标记保留
        assert result[0].profile_extras.get("_role_type_fallback") is True

    def test_apply_resolutions_accepts_same_protagonist(self):
        """如果 LLM 仲裁结果恰好也是 protagonist，正常应用（不拦截）。"""
        proto = make_person(
            "杨令珊",
            appearance_count=5,
            role_type="protagonist",
        )
        proto.profile_extras["_role_type_fallback"] = True
        proto.profile_extras["_role_type_original"] = "antagonist"

        resolutions = {("杨令珊", "role_type"): "protagonist"}
        result = apply_resolutions([proto], resolutions)
        assert result[0].role_type == "protagonist"
        # verified 标记应被加上
        assert result[0].profile_extras.get("verified") is True

    def test_apply_resolutions_non_fallback_normal_path(self):
        """非 fallback 的角色 → apply_resolutions 正常应用 LLM 结果。"""
        normal = make_person("普通角色", appearance_count=5, role_type="supporting")
        resolutions = {("普通角色", "role_type"): "antagonist"}
        result = apply_resolutions([normal], resolutions)
        # 正常应用
        assert result[0].role_type == "antagonist"


# ============================================================
# L5: character_archive _inferred 标记透传
# ============================================================


class TestL5InferredFlagPropagation:
    """V4.2.3 — _inferred 标记从 L2/L3 兜底正确透传到序列化 JSON。"""

    def test_l2_fallback_marked_as_inferred_in_archive(self):
        """L2 兜底升级的 protagonist 序列化时 _inferred=True + _inferred_original_role=原值。"""
        builder = CharacterArchiveBuilder()
        # 模拟 L2 已兜底
        proto = make_person("杨令珊", appearance_count=10, role_type="protagonist")
        proto.profile_extras["_role_type_fallback"] = True
        proto.profile_extras["_role_type_original"] = "antagonist"

        other = make_person("国师", appearance_count=5, role_type="antagonist")
        result = builder.build(entities=[proto, other], total_chapters=1)

        protos = result["protagonist_archetypes"]
        assert len(protos) == 1
        assert protos[0]["name"] == "杨令珊"
        assert protos[0]["_inferred"] is True
        assert protos[0]["_inferred_original_role"] == "antagonist"

    def test_l3_double_safety_marked_as_inferred(self):
        """L3 双保险兜底（_role_type_fallback 未设置但本层升级）→ 也带 _inferred=True。"""
        builder = CharacterArchiveBuilder()
        # 模拟 L2 完全没运行：所有 person 都是 antagonist 且无 _role_type_fallback
        persons = [
            make_person("杨令珊", appearance_count=10, role_type="antagonist"),
            make_person("国师", appearance_count=5, role_type="antagonist"),
        ]
        result = builder.build(entities=persons, total_chapters=1)
        protos = result["protagonist_archetypes"]
        assert len(protos) == 1
        assert protos[0]["name"] == "杨令珊"
        # L3 升级也应该带 _inferred=True
        assert protos[0]["_inferred"] is True
        # 没 _role_type_original 字段（L3 不知道原 LLM 标记是什么）
        assert "_inferred_original_role" not in protos[0]

    def test_normal_protagonist_no_inferred_flag(self):
        """正常 LLM 标记的 protagonist 不带 _inferred 标记。"""
        builder = CharacterArchiveBuilder()
        proto = make_person("正常主角", appearance_count=10, role_type="protagonist")
        # 不加任何 fallback 标记
        result = builder.build(entities=[proto], total_chapters=1)
        protos = result["protagonist_archetypes"]
        assert len(protos) == 1
        assert protos[0]["name"] == "正常主角"
        assert "_inferred" not in protos[0]
        assert "_inferred_original_role" not in protos[0]

    def test_l2_fallback_with_none_original_role(self):
        """L2 兜底时原 role_type=None → _inferred_original_role 字段不输出（避免冗余 null）。"""
        builder = CharacterArchiveBuilder()
        proto = make_person("无标记主角", appearance_count=5, role_type="protagonist")
        proto.profile_extras["_role_type_fallback"] = True
        proto.profile_extras["_role_type_original"] = None  # 原来就没标

        result = builder.build(entities=[proto], total_chapters=1)
        protos = result["protagonist_archetypes"]
        assert protos[0]["_inferred"] is True
        # _inferred_original_role 不应出现（节省 JSON 大小）
        assert "_inferred_original_role" not in protos[0]
