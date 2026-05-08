"""拆书 V3.1 Verification Pass 验收测试。

覆盖：
- ConflictDetector：3 类字段冲突识别 + 阈值边界 + 排序
- VerificationPass：mock LLM 仲裁 + 失败兜底 + 自创值过滤
- apply_resolutions：3 类字段回写 + null 处理 + verified 标记

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §3
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    EntityProfile,
    EntityType,
    LocationFact,
)
from app.services.book_dissect.verification_pass import (
    APPEARANCE_SIMILARITY_THRESHOLD,
    ConflictCandidate,
    ConflictDetector,
    EntityConflict,
    MAX_CONFLICTS_PER_CALL,
    ROLE_TYPE_DOMINANCE_THRESHOLD,
    ROLE_TYPE_MIN_VOTES,
    VerificationPass,
    apply_resolutions,
)


# ============================================================
# fixtures
# ============================================================


def make_person_entity(name: str, count: int = 5) -> EntityProfile:
    return EntityProfile(
        canonical_name=name,
        entity_type=EntityType.PERSON.value,
        aliases=[],
        first_chapter=1,
        last_chapter=count,
        appearance_count=count,
        role_type="supporting",
        profile_extras={"appearance": None, "abilities": [], "locations": []},
    )


def make_location_entity(name: str, type_: str = "宗门", count: int = 3) -> EntityProfile:
    return EntityProfile(
        canonical_name=name,
        entity_type=EntityType.LOCATION.value,
        aliases=[],
        first_chapter=1,
        last_chapter=count,
        appearance_count=count,
        role_type=None,
        profile_extras={"type": type_, "parent": None, "peers": [], "description": None},
    )


def make_chapter(
    chapter_number: int,
    *,
    characters: list[CharacterFact] | None = None,
    locations: list[LocationFact] | None = None,
) -> ChapterFact:
    return ChapterFact(
        chapter_number=chapter_number,
        chapter_title=f"第{chapter_number}章",
        summary=None,
        characters=characters or [],
        locations=locations or [],
    )


def mock_llm(json_obj: dict | str) -> MagicMock:
    ai = MagicMock()
    content = json.dumps(json_obj, ensure_ascii=False) if isinstance(json_obj, dict) else json_obj
    ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


# ============================================================
# ConflictDetector
# ============================================================


class TestConflictDetectorRoleType:
    def test_dispersed_votes_detected(self):
        """role_type 投票分散应识别为冲突。"""
        entity = make_person_entity("林七", count=10)
        # 5 票：3 supporting / 2 protagonist → 3/5 = 60% 边界，应不触发
        # 我们让 4 票：1 protagonist / 1 supporting / 1 minor / 1 antagonist → 25%
        facts = [
            make_chapter(1, characters=[CharacterFact(name="林七", role_hint="protagonist", evidence="主角出场")]),
            make_chapter(2, characters=[CharacterFact(name="林七", role_hint="supporting")]),
            make_chapter(3, characters=[CharacterFact(name="林七", role_hint="minor")]),
            make_chapter(4, characters=[CharacterFact(name="林七", role_hint="antagonist")]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        role_conflicts = [c for c in conflicts if c.field == "role_type"]
        assert len(role_conflicts) == 1
        c = role_conflicts[0]
        assert c.canonical_name == "林七"
        assert len(c.candidates) >= 2
        # evidence_chapters / evidence_texts 应填充
        assert all(cand.evidence_chapters for cand in c.candidates)

    def test_dominant_vote_skipped(self):
        """role_type 占比 ≥60% 不识别为冲突。"""
        entity = make_person_entity("林七")
        # 5 票全是 protagonist → 100% > 60%
        facts = [
            make_chapter(i, characters=[CharacterFact(name="林七", role_hint="protagonist")])
            for i in range(1, 6)
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        assert not any(c.field == "role_type" for c in conflicts)

    def test_low_vote_count_skipped(self):
        """票数 < ROLE_TYPE_MIN_VOTES 不进仲裁池。"""
        entity = make_person_entity("林七")
        # 仅 2 票 → 不达阈值
        facts = [
            make_chapter(1, characters=[CharacterFact(name="林七", role_hint="protagonist")]),
            make_chapter(2, characters=[CharacterFact(name="林七", role_hint="supporting")]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        assert not conflicts

    def test_alias_resolved_to_canonical(self):
        """alias_map 中的别名应归并到 canonical 后再统计。"""
        entity = make_person_entity("林七")
        facts = [
            make_chapter(1, characters=[CharacterFact(name="七哥", role_hint="protagonist")]),
            make_chapter(2, characters=[CharacterFact(name="林少", role_hint="supporting")]),
            make_chapter(3, characters=[CharacterFact(name="林七", role_hint="minor")]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect(
            [entity], facts, alias_map={"七哥": "林七", "林少": "林七"}
        )
        role_conflicts = [c for c in conflicts if c.field == "role_type"]
        assert len(role_conflicts) == 1
        assert role_conflicts[0].canonical_name == "林七"


class TestConflictDetectorAppearance:
    def test_two_distinct_appearances_detected(self):
        """两个明显不同的 appearance 描述应识别冲突。"""
        entity = make_person_entity("林七")
        facts = [
            make_chapter(3, characters=[
                CharacterFact(name="林七", appearance="瘦削少年，目光锐利", evidence="第三章描述")
            ]),
            make_chapter(80, characters=[
                CharacterFact(name="林七", appearance="高大青年，气宇轩昂", evidence="第八十章")
            ]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        ap_conflicts = [c for c in conflicts if c.field == "appearance"]
        assert len(ap_conflicts) == 1
        c = ap_conflicts[0]
        # 应有两个 bucket
        assert len(c.candidates) == 2

    def test_similar_appearances_merged(self):
        """相似度高的 appearance 应被合并到同一 bucket。"""
        entity = make_person_entity("林七")
        facts = [
            make_chapter(1, characters=[CharacterFact(name="林七", appearance="瘦削少年")]),
            make_chapter(2, characters=[CharacterFact(name="林七", appearance="瘦削少年")]),
            make_chapter(3, characters=[CharacterFact(name="林七", appearance="瘦削的少年")]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        # 三条几乎相同，应只产生一个 bucket → 不构成冲突
        ap_conflicts = [c for c in conflicts if c.field == "appearance"]
        assert not ap_conflicts

    def test_empty_appearance_ignored(self):
        """空 appearance 不应被纳入。"""
        entity = make_person_entity("林七")
        facts = [
            make_chapter(1, characters=[CharacterFact(name="林七", appearance=None)]),
            make_chapter(2, characters=[CharacterFact(name="林七", appearance="")]),
            make_chapter(3, characters=[CharacterFact(name="林七", appearance="瘦削少年")]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        ap_conflicts = [c for c in conflicts if c.field == "appearance"]
        assert not ap_conflicts


class TestConflictDetectorLocationType:
    def test_two_types_detected(self):
        entity = make_location_entity("青云宗", type_="宗门")
        facts = [
            make_chapter(1, locations=[LocationFact(name="青云宗", type="宗门", evidence="…宗门…")]),
            make_chapter(2, locations=[LocationFact(name="青云宗", type="宗门", evidence="千年宗门")]),
            make_chapter(3, locations=[LocationFact(name="青云宗", type="城池", evidence="城内…")]),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect([entity], facts, alias_map={})
        loc_conflicts = [c for c in conflicts if c.field == "location_type"]
        assert len(loc_conflicts) == 1
        c = loc_conflicts[0]
        # 票数应为 宗门=2 / 城池=1
        values = {cand.value: cand.vote_count for cand in c.candidates}
        assert values.get("宗门") == 2
        assert values.get("城池") == 1


class TestConflictDetectorOrdering:
    def test_top_n_capped(self):
        """超过 MAX_CONFLICTS_PER_CALL 应被截断。"""
        # 构造 N+5 个有冲突的实体
        entities = [make_person_entity(f"角色{i}", count=10) for i in range(MAX_CONFLICTS_PER_CALL + 5)]
        facts = []
        for i, e in enumerate(entities):
            facts.append(make_chapter(1, characters=[
                CharacterFact(name=e.canonical_name, role_hint="protagonist"),
                CharacterFact(name=e.canonical_name, role_hint="supporting"),
                CharacterFact(name=e.canonical_name, role_hint="minor"),
                CharacterFact(name=e.canonical_name, role_hint="antagonist"),
            ]))
        detector = ConflictDetector()
        conflicts = detector.detect(entities, facts, alias_map={})
        assert len(conflicts) <= MAX_CONFLICTS_PER_CALL

    def test_sorted_by_appearance_count_desc(self):
        """冲突应按 appearance_count 倒序。"""
        e1 = make_person_entity("角色A", count=3)
        e2 = make_person_entity("角色B", count=20)
        facts = []
        for name in ["角色A", "角色B"]:
            facts.append(make_chapter(1, characters=[
                CharacterFact(name=name, role_hint="protagonist"),
                CharacterFact(name=name, role_hint="supporting"),
                CharacterFact(name=name, role_hint="minor"),
            ]))
        detector = ConflictDetector()
        conflicts = detector.detect([e1, e2], facts, alias_map={})
        # 角色B（出场 20 次）应排在前
        names = [c.canonical_name for c in conflicts]
        assert names.index("角色B") < names.index("角色A")


class TestConflictDetectorEmpty:
    def test_no_entities(self):
        detector = ConflictDetector()
        assert detector.detect([], [make_chapter(1)], alias_map={}) == []

    def test_no_facts(self):
        detector = ConflictDetector()
        assert detector.detect([make_person_entity("林七")], [], alias_map={}) == []


# ============================================================
# VerificationPass
# ============================================================


def _make_role_conflict() -> EntityConflict:
    return EntityConflict(
        canonical_name="林七",
        field="role_type",
        candidates=[
            ConflictCandidate(value="protagonist", vote_count=3, evidence_chapters=[10, 12, 15]),
            ConflictCandidate(value="supporting", vote_count=2, evidence_chapters=[3, 5]),
        ],
        appearance_count=10,
    )


class TestVerificationPassResolve:
    @pytest.mark.asyncio
    async def test_normal_resolution(self):
        ai = mock_llm({
            "resolutions": [
                {"canonical_name": "林七", "field": "role_type",
                 "final_value": "protagonist", "reason": "后期 evidence 一致"}
            ]
        })
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        assert out == {("林七", "role_type"): "protagonist"}

    @pytest.mark.asyncio
    async def test_null_final_value(self):
        """LLM 返回 null final_value 应保留为 None（不覆盖原值）。"""
        ai = mock_llm({
            "resolutions": [
                {"canonical_name": "林七", "field": "role_type",
                 "final_value": None, "reason": "拿不准"}
            ]
        })
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        assert ("林七", "role_type") in out
        assert out[("林七", "role_type")] is None

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self):
        """LLM 调用失败应返回空 dict（不抛）。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock(side_effect=RuntimeError("API down"))
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        assert out == {}

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self):
        ai = mock_llm("not a json at all { bad")
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        assert out == {}

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": ""})
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        assert out == {}

    @pytest.mark.asyncio
    async def test_self_invented_value_filtered(self):
        """LLM 自创不在候选集中的值应被过滤。"""
        ai = mock_llm({
            "resolutions": [
                {"canonical_name": "林七", "field": "role_type",
                 "final_value": "hero", "reason": "..."}  # 'hero' 不在候选集
            ]
        })
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        # 自创值应被过滤
        assert ("林七", "role_type") not in out

    @pytest.mark.asyncio
    async def test_unknown_pair_filtered(self):
        """LLM 凭空生成不存在的 (name, field) 应被过滤。"""
        ai = mock_llm({
            "resolutions": [
                {"canonical_name": "不存在的角色", "field": "role_type",
                 "final_value": "protagonist", "reason": "..."}
            ]
        })
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([_make_role_conflict()])
        assert out == {}

    @pytest.mark.asyncio
    async def test_empty_conflicts_no_llm_call(self):
        """空 conflicts 应直接返回空，不调 LLM。"""
        ai = MagicMock()
        ai.generate_text = AsyncMock()
        v = VerificationPass(ai_service=ai)
        out = await v.resolve([])
        assert out == {}
        ai.generate_text.assert_not_called()


# ============================================================
# apply_resolutions
# ============================================================


class TestApplyResolutions:
    def test_role_type_overwritten(self):
        e = make_person_entity("林七")
        e.role_type = "supporting"
        out = apply_resolutions([e], {("林七", "role_type"): "protagonist"})
        assert out[0].role_type == "protagonist"
        assert out[0].profile_extras.get("verified") is True
        assert "role_type" in out[0].profile_extras.get("verified_fields", [])

    def test_appearance_overwritten(self):
        e = make_person_entity("林七")
        e.profile_extras["appearance"] = "瘦削少年"
        out = apply_resolutions([e], {("林七", "appearance"): "高大青年"})
        assert out[0].profile_extras["appearance"] == "高大青年"
        assert out[0].profile_extras["verified"] is True

    def test_location_type_overwritten(self):
        e = make_location_entity("青云宗", type_="城池")
        out = apply_resolutions([e], {("青云宗", "location_type"): "宗门"})
        assert out[0].profile_extras["type"] == "宗门"
        assert out[0].profile_extras["verified"] is True

    def test_null_resolution_does_not_overwrite_but_marks_verified(self):
        e = make_person_entity("林七")
        e.role_type = "supporting"
        out = apply_resolutions([e], {("林七", "role_type"): None})
        # 原值保留
        assert out[0].role_type == "supporting"
        # 但仍打标
        assert out[0].profile_extras["verified"] is True
        assert "role_type" in out[0].profile_extras["verified_fields"]

    def test_unknown_field_skipped(self):
        """未知字段应整体跳过：不污染实体也不污染 verified_fields。"""
        e = make_person_entity("林七")
        out = apply_resolutions([e], {("林七", "unknown_field"): "value"})
        # 未知字段不应修改实体
        assert out[0].role_type == "supporting"
        # 也不应进入 verified_fields（避免审计标记被污染）
        assert "unknown_field" not in out[0].profile_extras.get("verified_fields", [])

    def test_unknown_entity_skipped(self):
        e = make_person_entity("林七")
        out = apply_resolutions([e], {("不存在", "role_type"): "protagonist"})
        # 不应抛异常，只是跳过
        assert out[0].role_type == "supporting"

    def test_empty_resolutions_no_change(self):
        e = make_person_entity("林七")
        out = apply_resolutions([e], {})
        assert out[0].role_type == "supporting"
        assert "verified" not in out[0].profile_extras
