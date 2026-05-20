"""R2 单测：ReferencePackInjector 自身行为

覆盖：
- StrengthProfile 档位（light < medium < deep）
- resolve_dimensions：显式过滤 / 隐式并集 / fallback 兜底 / corpus 永远可用
- resolve_strength：显式优先 / 隐式取最深
- build_reference_block：含 user_segment / system_segment / user_sections /
  used_packs 元数据 / debug_meta；缺失维度降级；多 pack 合并

注：``resolve_packs`` 涉及 DB 加载，已被 ``test_book_dissect_v3_r5_imitation``
的端到端 fixture 覆盖；本文件聚焦纯逻辑层，不重复造 fixture。
"""

from __future__ import annotations

import json
from typing import List, Optional

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import database  # noqa: F401  注册所有模型
from app.db_base import Base
from app.models.project import Project
from app.models.project_reference_pack import ProjectReferencePack
from app.models.reference_pack import ReferencePack
from app.services.reference_pack_injector import (
    ReferenceBlock,
    ReferencePackInjector,
    StrengthProfile,
    _ResolvedPack,
)


# ============================================================
# 数据构造工具
# ============================================================


def make_pack(
    pack_id: str = "p1",
    title: str = "原书",
    *,
    methodology: Optional[dict] = None,
    style: Optional[dict] = None,
    structure: Optional[dict] = None,
    archetypes: Optional[dict] = None,
    worldbuilding: Optional[dict] = None,
    synopsis: Optional[dict] = None,  # V3.2 Tab6
    entities: Optional[dict] = None,  # V3.2-P2
    relations: Optional[dict] = None,  # V3.2-P2
    events: Optional[dict] = None,  # V3.2-P2
    generated_dimensions: Optional[List[str]] = None,
    default_dimensions: Optional[List[str]] = None,
    default_strength: str = "medium",
) -> _ResolvedPack:
    return _ResolvedPack(
        pack_id=pack_id,
        source_book_title=title,
        task_id=f"task-{pack_id}",
        methodology=methodology,
        style=style,
        structure=structure,
        archetypes=archetypes,
        worldbuilding=worldbuilding,
        generated_dimensions=generated_dimensions or [],
        default_dimensions=default_dimensions or [],
        default_strength=default_strength,
        synopsis=synopsis,
        entities=entities,
        relations=relations,
        events=events,
    )


# ============================================================
# 1) StrengthProfile 档位
# ============================================================


class TestStrengthProfile:
    def test_light_smaller_than_medium_smaller_than_deep(self):
        light = StrengthProfile.for_strength("light")
        medium = StrengthProfile.for_strength("medium")
        deep = StrengthProfile.for_strength("deep")
        for attr in (
            "methodology_chars",
            "structure_chars",
            "archetypes_chars",
            "worldbuilding_chars",
            "style_chars",
        ):
            assert getattr(light, attr) < getattr(medium, attr) < getattr(deep, attr)
        assert light.corpus_top_k < medium.corpus_top_k < deep.corpus_top_k

    def test_unknown_falls_back_to_medium(self):
        p = StrengthProfile.for_strength("unknown")
        assert p.name == "medium"

    def test_none_falls_back_to_medium(self):
        p = StrengthProfile.for_strength(None)  # type: ignore[arg-type]
        assert p.name == "medium"


# ============================================================
# 2) resolve_dimensions
# ============================================================


class TestResolveDimensions:
    def test_explicit_filtered_to_generated_plus_corpus(self):
        inj = ReferencePackInjector()
        packs = [make_pack(generated_dimensions=["methodology", "style"])]
        dims = inj.resolve_dimensions(
            packs, ["methodology", "structure", "corpus", "worldbuilding"]
        )
        assert "methodology" in dims
        assert "corpus" in dims
        assert "structure" not in dims  # 未生成
        assert "worldbuilding" not in dims

    def test_explicit_all_invalid_falls_back_to_corpus(self):
        inj = ReferencePackInjector()
        packs = [make_pack(generated_dimensions=["methodology"])]
        dims = inj.resolve_dimensions(packs, ["worldbuilding", "archetypes"])
        assert dims == ["corpus"]

    def test_implicit_uses_default_dimensions_union(self):
        inj = ReferencePackInjector()
        p1 = make_pack(
            "p1",
            generated_dimensions=["methodology", "style"],
            default_dimensions=["methodology", "corpus"],
        )
        p2 = make_pack(
            "p2",
            generated_dimensions=["structure"],
            default_dimensions=["structure"],
        )
        dims = inj.resolve_dimensions([p1, p2], None)
        assert set(dims) == {"methodology", "corpus", "structure"}

    def test_implicit_empty_default_uses_class_fallback(self):
        inj = ReferencePackInjector()
        # 故意让 default_dimensions 全空 + 已生成 methodology + style
        packs = [make_pack(generated_dimensions=["methodology", "style"])]
        dims = inj.resolve_dimensions(packs, None)
        # class 级 fallback = (methodology, style, corpus)
        assert set(dims) == {"methodology", "style", "corpus"}

    def test_explicit_fallback_overrides_class_default(self):
        inj = ReferencePackInjector()
        packs = [make_pack(generated_dimensions=["worldbuilding"])]
        # 用方法参数提供专属 fallback
        dims = inj.resolve_dimensions(
            packs,
            None,
            fallback=("worldbuilding",),
        )
        assert dims == ["worldbuilding"]

    def test_corpus_always_available_even_without_generation(self):
        inj = ReferencePackInjector()
        packs = [make_pack(generated_dimensions=[])]  # 没有任何 5 维生成
        dims = inj.resolve_dimensions(packs, ["corpus"])
        assert dims == ["corpus"]


# ============================================================
# 3) resolve_strength
# ============================================================


class TestResolveStrength:
    def test_explicit_wins(self):
        inj = ReferencePackInjector()
        packs = [make_pack(default_strength="light")]
        assert inj.resolve_strength(packs, "deep") == "deep"

    def test_implicit_takes_max(self):
        inj = ReferencePackInjector()
        packs = [
            make_pack("a", default_strength="light"),
            make_pack("b", default_strength="deep"),
            make_pack("c", default_strength="medium"),
        ]
        assert inj.resolve_strength(packs, None) == "deep"

    def test_implicit_only_light(self):
        inj = ReferencePackInjector()
        packs = [make_pack(default_strength="light")]
        assert inj.resolve_strength(packs, None) == "light"

    def test_implicit_no_packs_defaults_medium(self):
        inj = ReferencePackInjector()
        assert inj.resolve_strength([], None) == "medium"


# ============================================================
# 4) build_reference_block 集成（含 DB 数据）
# ============================================================


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_project_with_pack(
    sess: AsyncSession,
    *,
    style_content: str = "冷静克制的笔法，短句细描",
    methodology_content: str = "金手指：随机抽奖；爽点节奏：3-5 章一波",
    default_dimensions: Optional[List[str]] = None,
) -> tuple[Project, ReferencePack]:
    proj = Project(
        id="proj-1",
        user_id="u1",
        title="测试项目",
        theme="修真",
        narrative_perspective="第三人称",
    )
    sess.add(proj)
    pack = ReferencePack(
        id="pack-1",
        user_id="u1",
        task_id="task-1",
        source_book_title="对标原书",
        methodology_json=json.dumps(
            {"prompt_content": methodology_content}, ensure_ascii=False
        ),
        style_json=json.dumps({"prompt_content": style_content}, ensure_ascii=False),
        status="ready",
        generated_dimensions=json.dumps(["methodology", "style"], ensure_ascii=False),
    )
    sess.add(pack)
    link = ProjectReferencePack(
        project_id=proj.id,
        pack_id=pack.id,
        default_dimensions=json.dumps(
            default_dimensions or ["methodology", "style", "corpus"],
            ensure_ascii=False,
        ),
        default_strength="medium",
    )
    sess.add(link)
    await sess.commit()
    return proj, pack


class TestBuildReferenceBlock:
    @pytest.mark.asyncio
    async def test_returns_user_and_system_segments(self, session_factory):
        async with session_factory() as sess:
            proj, _pack = await _seed_project_with_pack(sess)
            inj = ReferencePackInjector()
            block = await inj.build_reference_block(
                sess,
                proj.id,
                scene="story_outline",
                anchor_query="主角第一次抽奖",
            )
        assert isinstance(block, ReferenceBlock)
        assert "金手指" in block.user_segment  # methodology 进 user
        assert "冷静克制" in block.system_segment  # style 进 system
        assert "methodology" in block.used_dimensions
        assert "style" in block.used_dimensions
        assert block.used_strength == "medium"
        assert block.debug_meta["scene"] == "story_outline"
        assert block.debug_meta["pack_count"] == 1
        # user_sections 与 user_segment 行为一致（join 后等价于 user_segment）
        assert "\n\n".join(block.user_sections) == block.user_segment

    @pytest.mark.asyncio
    async def test_used_packs_metadata_per_pack(self, session_factory):
        async with session_factory() as sess:
            proj, pack = await _seed_project_with_pack(sess)
            inj = ReferencePackInjector()
            block = await inj.build_reference_block(
                sess, proj.id, scene="generic", anchor_query="x"
            )
        assert len(block.used_packs) == 1
        meta = block.used_packs[0]
        assert meta["pack_id"] == pack.id
        assert meta["source_book_title"] == "对标原书"
        # 当前 pack 提供 methodology/style 两维 + corpus（永远可用）
        assert set(meta["dimensions"]) >= {"methodology", "style", "corpus"}

    @pytest.mark.asyncio
    async def test_explicit_dimensions_override(self, session_factory):
        async with session_factory() as sess:
            proj, _ = await _seed_project_with_pack(sess)
            inj = ReferencePackInjector()
            # 显式只要 methodology
            block = await inj.build_reference_block(
                sess,
                proj.id,
                dimensions=["methodology"],
                anchor_query="x",
            )
        assert block.used_dimensions == ["methodology"]
        assert block.system_segment == ""  # style 未启用，system 段为空
        assert "金手指" in block.user_segment

    @pytest.mark.asyncio
    async def test_explicit_strength_override(self, session_factory):
        async with session_factory() as sess:
            proj, _ = await _seed_project_with_pack(sess)
            inj = ReferencePackInjector()
            light_block = await inj.build_reference_block(
                sess, proj.id, strength="light", anchor_query="x"
            )
            deep_block = await inj.build_reference_block(
                sess, proj.id, strength="deep", anchor_query="x"
            )
        assert light_block.used_strength == "light"
        assert deep_block.used_strength == "deep"
        # deep 强度的 system_segment（style）应不短于 light（同样源数据）
        assert len(deep_block.system_segment) >= len(light_block.system_segment)

    @pytest.mark.asyncio
    async def test_corpus_skipped_without_anchor(self, session_factory):
        async with session_factory() as sess:
            proj, _ = await _seed_project_with_pack(sess)
            inj = ReferencePackInjector()
            block = await inj.build_reference_block(
                sess, proj.id, dimensions=["corpus"], anchor_query=None
            )
        # 即便用户显式要 corpus，没有 anchor_query 时跳过（无锚检索没意义）
        # 维度仍被记入 used_dimensions（用户意图），但实际 user_segment 为空
        assert "corpus" in block.used_dimensions
        assert block.user_segment == ""

    @pytest.mark.asyncio
    async def test_no_attached_pack_raises(self, session_factory):
        async with session_factory() as sess:
            proj = Project(
                id="proj-empty",
                user_id="u1",
                title="无挂载项目",
                theme="x",
            )
            sess.add(proj)
            await sess.commit()
            inj = ReferencePackInjector()
            with pytest.raises(ValueError, match="未挂载"):
                await inj.build_reference_block(
                    sess, proj.id, anchor_query="x"
                )


# ============================================================
# 5) V3.2 synopsis 复活：_format_synopsis + Story Bible 层注入
# ============================================================


class TestSynopsisFormat:
    """验收 V3.2 synopsis 维度的端到端注入行为。"""

    SAMPLE_SYNOPSIS = {
        "genre_tag": "仙侠",
        "core_premise": "少年因家族变故踏入修行路，揭开身世之谜。",
        "golden_finger_concept": "传承流",
        "power_system_overview": "境界等级（炼气-筑基-金丹）",
        "central_conflict": "复仇 + 争霸",
        "ultimate_goal": "成神成圣",
        "selling_points": ["爽文", "打脸", "装逼"],
        "target_audience_signals": "男频热血型",
    }

    def test_format_synopsis_includes_all_fields(self):
        inj = ReferencePackInjector()
        pack = make_pack(synopsis=self.SAMPLE_SYNOPSIS)
        profile = StrengthProfile.for_strength("medium")
        text = inj._format_synopsis([pack], profile)
        assert text  # 非空
        # 8 个字段都应有 label
        assert "题材" in text and "仙侠" in text
        assert "故事前提" in text
        assert "金手指" in text and "传承流" in text
        assert "力量体系" in text
        assert "核心冲突" in text
        assert "终极目标" in text
        assert "卖点" in text
        # 列表渲染成 / 分隔
        assert "爽文 / 打脸 / 装逼" in text
        assert "目标受众" in text

    def test_format_synopsis_skips_pack_without_synopsis(self):
        inj = ReferencePackInjector()
        pack = make_pack(synopsis=None)
        text = inj._format_synopsis([pack], StrengthProfile.for_strength("medium"))
        assert text == ""

    def test_format_synopsis_includes_storybible_disclaimer(self):
        """注入文本必须含「禁止复刻」声明，防 LLM 抄具体名词。"""
        inj = ReferencePackInjector()
        pack = make_pack(synopsis=self.SAMPLE_SYNOPSIS)
        text = inj._format_synopsis([pack], StrengthProfile.for_strength("medium"))
        assert "仅供方向参考" in text
        assert "禁止复刻" in text

    def test_format_synopsis_truncates_to_strength_chars(self):
        """deep > medium > light 应满足字符上限关系。"""
        inj = ReferencePackInjector()
        # 构造一个长 synopsis（不会超 deep 上限但会被 light 截断）
        long_premise = "a" * 5000
        pack = make_pack(synopsis={**self.SAMPLE_SYNOPSIS, "core_premise": long_premise})
        light = inj._format_synopsis([pack], StrengthProfile.for_strength("light"))
        deep = inj._format_synopsis([pack], StrengthProfile.for_strength("deep"))
        assert len(light) < len(deep)

    def test_resolve_dimensions_synopsis_filtered_when_not_generated(self):
        """V3.2：用户传 synopsis 维度，但 pack 未生成 → 应被过滤掉。"""
        inj = ReferencePackInjector()
        pack = make_pack(generated_dimensions=["methodology"])  # 没有 synopsis
        dims = inj.resolve_dimensions(pack and [pack], ["synopsis"])
        # 全无效 fallback 到 corpus
        assert dims == ["corpus"]

    def test_resolve_dimensions_synopsis_kept_when_generated(self):
        """V3.2：pack 已生成 synopsis → 用户传 synopsis 应保留。"""
        inj = ReferencePackInjector()
        pack = make_pack(generated_dimensions=["synopsis", "methodology"])
        dims = inj.resolve_dimensions([pack], ["synopsis"])
        assert "synopsis" in dims

    def test_class_default_fallback_includes_synopsis(self):
        """V3.2：DEFAULT_DIMENSION_FALLBACK 应含 synopsis（让新拆任务自动启用）。"""
        assert "synopsis" in ReferencePackInjector.DEFAULT_DIMENSION_FALLBACK


class TestSynopsisStrengthProfile:
    def test_synopsis_chars_monotonic(self):
        """synopsis_chars 应满足 light < medium < deep。"""
        light = StrengthProfile.for_strength("light")
        medium = StrengthProfile.for_strength("medium")
        deep = StrengthProfile.for_strength("deep")
        assert light.synopsis_chars < medium.synopsis_chars < deep.synopsis_chars


# ============================================================
# V3.2-P2：模式三维度 entities/relations/events 格式化
# ============================================================


class TestPatternStrengthProfile:
    def test_entities_relations_events_chars_monotonic(self):
        """V3.2-P2 三个模式维度的字符上限也应满足 light < medium < deep。"""
        light = StrengthProfile.for_strength("light")
        medium = StrengthProfile.for_strength("medium")
        deep = StrengthProfile.for_strength("deep")
        for attr in ("entities_chars", "relations_chars", "events_chars"):
            assert getattr(light, attr) < getattr(medium, attr) < getattr(deep, attr)


class TestEntitiesFormat:
    SAMPLE = {
        "type_distribution": {"person": 12, "location": 6, "item": 3},
        "role_distribution": {"protagonist": 1, "supporting": 8},
        "naming_style_signals": {
            "length_distribution": {2: 5, 3: 8},
            "cn_to_other_ratio": 0.95,
            "top_first_char_diversity": 0.4,
        },
        "main_role_archetype_count": 1,
        "total_entities": 21,
    }

    def test_format_includes_signals(self):
        inj = ReferencePackInjector()
        pack = make_pack(entities=self.SAMPLE)
        text = inj._format_entities([pack], StrengthProfile.for_strength("medium"))
        assert text
        assert "实体类型分布" in text
        assert "角色档位分布" in text
        assert "命名长度分布" in text
        assert "主线主角数" in text
        assert "禁止复刻" in text  # 有 V3 哲学隐私警告

    def test_format_skips_pack_without_entities(self):
        inj = ReferencePackInjector()
        pack = make_pack(entities=None)
        text = inj._format_entities([pack], StrengthProfile.for_strength("medium"))
        assert text == ""


class TestRelationsFormat:
    SAMPLE = {
        "category_distribution": {"family": 4, "hostile": 6},
        "top_relation_types": {"father": 3, "rival": 5},
        "avg_occurrence_count": 2.5,
        "total_relations": 10,
    }

    def test_format_includes_categories(self):
        inj = ReferencePackInjector()
        pack = make_pack(relations=self.SAMPLE)
        text = inj._format_relations([pack], StrengthProfile.for_strength("medium"))
        assert "关系类别分布" in text
        assert "高频关系类型" in text
        assert "平均跨章节强度" in text
        assert "禁止复刻" in text

    def test_format_skips_pack_without_relations(self):
        inj = ReferencePackInjector()
        pack = make_pack(relations=None)
        text = inj._format_relations([pack], StrengthProfile.for_strength("medium"))
        assert text == ""


class TestEventsFormat:
    SAMPLE = {
        "type_distribution": {"fight": 12, "breakthrough": 8},
        "importance_distribution": {"high": 5, "medium": 10, "low": 5},
        "high_importance_chapter_density": 4.0,
        "total_chapters": 20,
        "total_events": 20,
    }

    def test_format_includes_density(self):
        inj = ReferencePackInjector()
        pack = make_pack(events=self.SAMPLE)
        text = inj._format_events([pack], StrengthProfile.for_strength("medium"))
        assert "事件类型分布" in text
        assert "重要性分布" in text
        assert "高重要性事件密度" in text
        assert "4.0" in text or "4" in text  # density 4.0
        assert "禁止复刻" in text

    def test_format_skips_pack_without_events(self):
        inj = ReferencePackInjector()
        pack = make_pack(events=None)
        text = inj._format_events([pack], StrengthProfile.for_strength("medium"))
        assert text == ""


class TestPatternResolveDimensions:
    """验证新三维度在 resolve_dimensions 中的过滤与保留逻辑。"""

    def test_explicit_entities_filtered_when_not_generated(self):
        """老拆包未生成 entities 时，显式选 entities 应被过滤。"""
        inj = ReferencePackInjector()
        packs = [make_pack(generated_dimensions=["methodology"])]
        dims = inj.resolve_dimensions(packs, ["entities", "relations", "events"])
        # 全部未生成 → 兑底 corpus
        assert "entities" not in dims
        assert "relations" not in dims
        assert "events" not in dims
        assert dims == ["corpus"]

    def test_explicit_entities_kept_when_generated(self):
        """V3.2-P2 生成了 entities 时，显式选 entities 应保留。"""
        inj = ReferencePackInjector()
        packs = [make_pack(generated_dimensions=["methodology", "entities", "relations", "events"])]
        dims = inj.resolve_dimensions(packs, ["entities", "relations", "events"])
        assert "entities" in dims
        assert "relations" in dims
        assert "events" in dims
