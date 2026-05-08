"""拆书 V3 R5 验收测试：一键仿写（参考包 → 项目章节草稿）

策略与 R3 一致：构造最小 FastAPI app，仅注册 imitation router；
依赖覆盖：
- get_db → 内存 sqlite
- get_user_ai_service → FakeAIService（不打外网）
- request.state.user_id → 中间件未启用，因此通过手动 mock 一个简单 ASGI middleware

覆盖：
- ImitationService.resolve_packs：显式/隐式/未挂载/未就绪
- resolve_dimensions：显式 ∩ 已生成；隐式取并集；corpus 永远可用
- resolve_strength：显式优先；隐式取最深
- assemble_prompt：项目状态/意图/5 维度/语料/字数；强度差异；style 进 system
- preview API：权限/校验/输出
- stream API：SSE 事件序列与权限
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware

from app import database  # noqa: F401  注册所有模型
from app.api import imitation as imit_api
from app.api.settings import get_user_ai_service
from app.database import get_db
from app.db_base import Base
from app.models.book_dissect_chapter_fact import BookDissectChapterFact
from app.models.book_dissect_task import BookDissectTask
from app.models.chapter import Chapter
from app.models.chapter_outline import ChapterOutline
from app.models.character import Character
from app.models.project import Project
from app.models.project_reference_pack import ProjectReferencePack
from app.models.reference_pack import ReferencePack
from app.models.writing_style import WritingStyle
from app.services.imitation_service import (
    ImitationService,
    StrengthProfile,
    _score_text,
    _tokenize_keywords,
)


# ============================================================
# Fixtures
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


# ============================================================
# Fake AI service
# ============================================================


class FakeAIService:
    """duck-typed AIService：仅实现 generate_text_stream。"""

    def __init__(self, chunks: List[str]):
        self.chunks = chunks
        self.last_prompt: Optional[str] = None
        self.last_system: Optional[str] = None

    async def generate_text_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        self.last_prompt = prompt
        self.last_system = system_prompt
        for c in self.chunks:
            yield c


# ============================================================
# Seed helpers
# ============================================================


async def _seed_pack(
    sess: AsyncSession,
    user_id: str,
    *,
    task_id: str = "task-1",
    pack_status: str = "ready",
    book_title: str = "原书.txt",
    methodology=None,
    style=None,
    structure=None,
    archetypes=None,
    worldbuilding=None,
    chapter_facts: Optional[List[Dict]] = None,
) -> ReferencePack:
    task = BookDissectTask(
        id=task_id,
        user_id=user_id,
        status="completed",
        file_name=book_title,
        chapter_count=10,
        total_words=10000,
        version=2,
    )
    sess.add(task)
    await sess.flush()

    generated = []
    if methodology:
        generated.append("methodology")
    if style:
        generated.append("style")
    if structure:
        generated.append("structure")
    if archetypes:
        generated.append("archetypes")
    if worldbuilding:
        generated.append("worldbuilding")

    pack = ReferencePack(
        user_id=user_id,
        task_id=task.id,
        source_book_title=book_title,
        methodology_json=json.dumps(methodology, ensure_ascii=False) if methodology else None,
        style_json=json.dumps(style, ensure_ascii=False) if style else None,
        structure_json=json.dumps(structure, ensure_ascii=False) if structure else None,
        archetypes_json=json.dumps(archetypes, ensure_ascii=False) if archetypes else None,
        worldbuilding_json=json.dumps(worldbuilding, ensure_ascii=False) if worldbuilding else None,
        status=pack_status,
        generated_dimensions=json.dumps(generated, ensure_ascii=False),
    )
    sess.add(pack)
    await sess.flush()

    if chapter_facts:
        for cf in chapter_facts:
            sess.add(
                BookDissectChapterFact(
                    task_id=task.id,
                    chapter_number=cf["chapter_number"],
                    chapter_title=cf.get("chapter_title", f"第{cf['chapter_number']}章"),
                    summary=cf.get("summary", ""),
                    extraction_status="completed",
                )
            )
        await sess.flush()
    return pack


async def _seed_project(
    sess: AsyncSession,
    user_id: str,
    *,
    project_id: str = "proj-1",
    title: str = "我的小说",
    genre: str = "玄幻",
    theme: str = "凡人逆袭",
) -> Project:
    proj = Project(
        id=project_id,
        user_id=user_id,
        title=title,
        description="测试项目",
        theme=theme,
        genre=genre,
        narrative_perspective="第三人称",
        target_words=100000,
        current_words=0,
        status="planning",
        wizard_status="incomplete",
        wizard_step=0,
        world_time_period="架空东方",
        world_location="云岚大陆",
        world_atmosphere="紧张刺激",
        world_rules="修炼体系：练气-筑基-金丹",
    )
    sess.add(proj)
    await sess.flush()
    return proj


async def _seed_character(
    sess: AsyncSession,
    project_id: str,
    name: str,
    role_type: str = "protagonist",
    personality: str = "坚毅果敢",
) -> Character:
    c = Character(
        project_id=project_id,
        name=name,
        role_type=role_type,
        personality=personality,
        gender="男",
        age="18",
    )
    sess.add(c)
    await sess.flush()
    return c


async def _attach(
    sess: AsyncSession,
    project_id: str,
    pack_id: str,
    *,
    dims: List[str],
    strength: str = "medium",
) -> ProjectReferencePack:
    link = ProjectReferencePack(
        project_id=project_id,
        pack_id=pack_id,
        default_dimensions=json.dumps(dims, ensure_ascii=False),
        default_strength=strength,
    )
    sess.add(link)
    await sess.flush()
    return link


# ============================================================
# 1) Service：resolve_packs / dimensions / strength
# ============================================================


class TestResolve:
    @pytest.mark.asyncio
    async def test_implicit_uses_all_attached_ready(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p1 = await _seed_pack(sess, "u-A", task_id="t-1", methodology={"prompt_content": "m1"})
            p2 = await _seed_pack(sess, "u-A", task_id="t-2", style={"prompt_content": "s2"})
            await _attach(sess, proj.id, p1.id, dims=["methodology"])
            await _attach(sess, proj.id, p2.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            packs = await svc.resolve_packs(sess, proj.id, None)
            assert {p.pack_id for p in packs} == {p1.id, p2.id}

    @pytest.mark.asyncio
    async def test_explicit_must_be_mounted(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p1 = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "s1"})
            await _attach(sess, proj.id, p1.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            with pytest.raises(ValueError, match="未挂载"):
                await svc.resolve_packs(sess, proj.id, ["pack-not-attached"])

    @pytest.mark.asyncio
    async def test_no_attachment_raises(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            await sess.commit()
            svc = ImitationService(FakeAIService([]))
            with pytest.raises(ValueError, match="未挂载"):
                await svc.resolve_packs(sess, proj.id, None)

    @pytest.mark.asyncio
    async def test_skips_unready_packs(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p_gen = await _seed_pack(
                sess, "u-A", task_id="t-1", pack_status="generating",
            )
            p_ok = await _seed_pack(
                sess, "u-A", task_id="t-2", style={"prompt_content": "s"}
            )
            await _attach(sess, proj.id, p_gen.id, dims=["style"])
            await _attach(sess, proj.id, p_ok.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            packs = await svc.resolve_packs(sess, proj.id, None)
            assert {p.pack_id for p in packs} == {p_ok.id}

    @pytest.mark.asyncio
    async def test_all_unready_raises(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p = await _seed_pack(sess, "u-A", task_id="t-1", pack_status="failed")
            await _attach(sess, proj.id, p.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            with pytest.raises(ValueError, match="均未就绪"):
                await svc.resolve_packs(sess, proj.id, None)

    @pytest.mark.asyncio
    async def test_dimensions_explicit_filters_to_generated_plus_corpus(
        self, session_factory
    ):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            # 该 pack 只生成了 style；用户显式请求 deep 全维度
            p = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "s"})
            await _attach(sess, proj.id, p.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            packs = await svc.resolve_packs(sess, proj.id, None)
            dims = svc.resolve_dimensions(
                packs, ["methodology", "style", "structure", "archetypes", "worldbuilding", "corpus"]
            )
            # methodology/structure/archetypes/worldbuilding 被过滤；style + corpus 保留
            assert set(dims) == {"style", "corpus"}

    @pytest.mark.asyncio
    async def test_dimensions_implicit_union_of_defaults(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p1 = await _seed_pack(
                sess, "u-A", task_id="t-1",
                methodology={"prompt_content": "m"},
                style={"prompt_content": "s"},
            )
            p2 = await _seed_pack(
                sess, "u-A", task_id="t-2",
                structure={"prompt_content": "st"},
            )
            await _attach(sess, proj.id, p1.id, dims=["methodology", "corpus"])
            await _attach(sess, proj.id, p2.id, dims=["structure"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            packs = await svc.resolve_packs(sess, proj.id, None)
            dims = svc.resolve_dimensions(packs, None)
            # 并集 ∩ 已生成 = {methodology, corpus, structure}
            assert set(dims) == {"methodology", "corpus", "structure"}

    @pytest.mark.asyncio
    async def test_dimensions_invalid_explicit_falls_back_to_corpus(
        self, session_factory
    ):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            # 该 pack 只生成 style；用户显式只请求 worldbuilding（无效）
            p = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "s"})
            await _attach(sess, proj.id, p.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            packs = await svc.resolve_packs(sess, proj.id, None)
            dims = svc.resolve_dimensions(packs, ["worldbuilding"])
            # 用户给的全无效 → 兜底 corpus
            assert dims == ["corpus"]

    def test_strength_explicit_wins(self):
        svc = ImitationService(FakeAIService([]))
        from app.services.imitation_service import _ResolvedPack

        packs = [
            _ResolvedPack(
                pack_id="x", source_book_title="x", task_id="t",
                methodology=None, style=None, structure=None,
                archetypes=None, worldbuilding=None,
                generated_dimensions=[], default_dimensions=[],
                default_strength="light",
            ),
        ]
        assert svc.resolve_strength(packs, "deep") == "deep"

    def test_strength_implicit_max(self):
        svc = ImitationService(FakeAIService([]))
        from app.services.imitation_service import _ResolvedPack

        def mk(s):
            return _ResolvedPack(
                pack_id="x", source_book_title="x", task_id="t",
                methodology=None, style=None, structure=None,
                archetypes=None, worldbuilding=None,
                generated_dimensions=[], default_dimensions=[],
                default_strength=s,
            )

        assert svc.resolve_strength([mk("light"), mk("deep"), mk("medium")], None) == "deep"
        assert svc.resolve_strength([mk("light"), mk("medium")], None) == "medium"
        assert svc.resolve_strength([mk("light")], None) == "light"


# ============================================================
# 2) Service：assemble_prompt
# ============================================================


class TestAssemble:
    @pytest.mark.asyncio
    async def test_assemble_includes_project_state_and_intent(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A", title="逆天传")
            await _seed_character(sess, proj.id, "李逸", "protagonist", "坚毅")
            p = await _seed_pack(
                sess, "u-A", task_id="t-1",
                methodology={"prompt_content": "金手指：测试石异象"},
                style={"prompt_content": "用短句、白描"},
            )
            await _attach(sess, proj.id, p.id, dims=["methodology", "style"], strength="medium")
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            bundle = await svc.assemble_prompt(
                sess,
                proj.id,
                user_intent="主角第一次测试灵根",
                target_chapter_id=None,
                pack_ids=None,
                dimensions=None,
                strength=None,
                target_word_count=1500,
            )

            assert "逆天传" in bundle["user_prompt"]
            assert "李逸" in bundle["user_prompt"]
            assert "主角第一次测试灵根" in bundle["user_prompt"]
            assert "参考方法论" in bundle["user_prompt"]
            assert "金手指：测试石异象" in bundle["user_prompt"]
            # style 进 system
            assert "用短句、白描" in bundle["system_prompt"]
            # 维度合并
            assert set(bundle["used_dimensions"]) == {"methodology", "style"}
            assert bundle["strength"] == "medium"
            assert bundle["target_word_count"] == 1500

    @pytest.mark.asyncio
    async def test_assemble_target_chapter_inserts_outline_and_recent(
        self, session_factory
    ):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            # 章纲 + 章节
            ol = ChapterOutline(
                project_id=proj.id,
                chapter_number=2,
                title="觉醒",
                summary="主角觉醒灵根",
                plot_points="测试石爆裂；众人惊呼；主角离开测试场",
                target_word_count=2000,
            )
            sess.add(ol)
            await sess.flush()
            ch_prev = Chapter(
                project_id=proj.id,
                chapter_number=1,
                title="序章",
                content="一段前置内容。" * 20,
                word_count=200,
            )
            ch_target = Chapter(
                project_id=proj.id,
                chapter_outline_id=ol.id,
                chapter_number=2,
                title="觉醒",
                content="",
            )
            sess.add(ch_prev)
            sess.add(ch_target)
            await sess.flush()

            p = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "白描"})
            await _attach(sess, proj.id, p.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            bundle = await svc.assemble_prompt(
                sess,
                proj.id,
                user_intent="承接序章，写主角进入测试现场",
                target_chapter_id=ch_target.id,
                pack_ids=None,
                dimensions=None,
                strength=None,
                target_word_count=1200,
            )
            assert "第2章《觉醒》" in bundle["user_prompt"]
            assert "测试石爆裂" in bundle["user_prompt"]  # plot_points 注入
            assert "第1章《序章》" in bundle["user_prompt"]  # 最近章节注入

    @pytest.mark.asyncio
    async def test_assemble_strength_light_shorter_than_deep(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            big_text = "段落。" * 600  # ≈ 1800 chars
            p = await _seed_pack(
                sess, "u-A", task_id="t-1",
                methodology={"prompt_content": big_text},
                structure={"prompt_content": big_text},
                archetypes={"prompt_content": big_text},
                worldbuilding={"prompt_content": big_text},
            )
            await _attach(
                sess, proj.id, p.id,
                dims=["methodology", "structure", "archetypes", "worldbuilding"],
            )
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            light = await svc.assemble_prompt(
                sess, proj.id,
                user_intent="写一段冲突",
                target_chapter_id=None, pack_ids=None,
                dimensions=["methodology", "structure", "archetypes", "worldbuilding"],
                strength="light", target_word_count=1500,
            )
            deep = await svc.assemble_prompt(
                sess, proj.id,
                user_intent="写一段冲突",
                target_chapter_id=None, pack_ids=None,
                dimensions=["methodology", "structure", "archetypes", "worldbuilding"],
                strength="deep", target_word_count=1500,
            )
            assert light["reference_chars"] < deep["reference_chars"]
            # light 强度下，每个维度上限 600 字符 → 4 个维度 ≤ 2400 + 标题
            assert light["reference_chars"] < 4000
            # deep 强度下，更接近 4 * 1800 ≈ 7200
            assert deep["reference_chars"] > 5000

    @pytest.mark.asyncio
    async def test_assemble_corpus_top_k_by_strength(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            facts = [
                {"chapter_number": i, "summary": f"主角{('测试' if i % 2 else '修炼')}灵根章 {i}"}
                for i in range(1, 6)
            ]
            p = await _seed_pack(
                sess, "u-A", task_id="t-1",
                style={"prompt_content": "白描"},
                chapter_facts=facts,
            )
            await _attach(sess, proj.id, p.id, dims=["corpus"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))

            for strength, expected_top in [("light", 1), ("medium", 2), ("deep", 3)]:
                bundle = await svc.assemble_prompt(
                    sess, proj.id,
                    user_intent="主角第一次测试灵根",  # 命中 "测试" "灵根"
                    target_chapter_id=None,
                    pack_ids=None,
                    dimensions=["corpus"],
                    strength=strength,
                    target_word_count=1500,
                )
                # 计数 "原书" 段落标号
                hits = bundle["user_prompt"].count("第") - 1  # 项目状态里没有"第X章"
                # 直接数 corpus bullet 行
                lines = [l for l in bundle["user_prompt"].split("\n") if l.startswith("- ")]
                assert len(lines) == expected_top, f"strength={strength}"

    @pytest.mark.asyncio
    async def test_assemble_no_style_dim_no_style_in_system(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p = await _seed_pack(
                sess, "u-A", task_id="t-1",
                methodology={"prompt_content": "M"},
                style={"prompt_content": "STYLE_TOKEN_XYZ"},
            )
            await _attach(sess, proj.id, p.id, dims=["methodology"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            bundle = await svc.assemble_prompt(
                sess, proj.id,
                user_intent="x",
                target_chapter_id=None,
                pack_ids=None,
                dimensions=["methodology"],  # 不勾 style
                strength="medium",
                target_word_count=1000,
            )
            assert "STYLE_TOKEN_XYZ" not in bundle["system_prompt"]
            assert "STYLE_TOKEN_XYZ" not in bundle["user_prompt"]

    @pytest.mark.asyncio
    async def test_assemble_with_project_writing_style(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            ws = WritingStyle(
                project_id=proj.id,
                name="个人风格",
                style_type="custom",
                prompt_content="WS_TOKEN_PROJECT",
            )
            sess.add(ws)
            await sess.flush()
            p = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "S_PACK"})
            await _attach(sess, proj.id, p.id, dims=["style"])
            await sess.commit()

            svc = ImitationService(FakeAIService([]))
            bundle = await svc.assemble_prompt(
                sess, proj.id,
                user_intent="x",
                target_chapter_id=None,
                pack_ids=None,
                dimensions=["style"],
                strength="medium",
                target_word_count=1000,
                style_id=ws.id,
            )
            assert "WS_TOKEN_PROJECT" in bundle["system_prompt"]
            assert "S_PACK" in bundle["system_prompt"]


# ============================================================
# 3) Tokenizer / corpus scoring (pure functions)
# ============================================================


class TestTokenization:
    def test_chinese_2gram(self):
        toks = _tokenize_keywords("主角测试灵根")
        # 应当包含连续 2-gram
        assert "主角" in toks
        assert "测试" in toks
        assert "灵根" in toks

    def test_english_words(self):
        toks = _tokenize_keywords("hello AI 测试")
        assert "hello" in toks
        assert "ai" in toks
        assert "测试" in toks

    def test_score_text_counts_keywords(self):
        kws = ["测试", "灵根"]
        assert _score_text("主角第一次测试灵根，测试石爆裂", kws) == 2
        assert _score_text("无关内容", kws) == 0


# ============================================================
# 4) StrengthProfile 配置
# ============================================================


class TestStrengthProfile:
    def test_light_lower_than_deep(self):
        light = StrengthProfile.for_strength("light")
        deep = StrengthProfile.for_strength("deep")
        assert light.methodology_chars < deep.methodology_chars
        assert light.structure_chars < deep.structure_chars
        assert light.style_chars < deep.style_chars
        assert light.corpus_top_k <= deep.corpus_top_k

    def test_unknown_falls_back_to_medium(self):
        prof = StrengthProfile.for_strength("invalid")
        assert prof.name == "medium"


# ============================================================
# 5) API：preview / stream
# ============================================================


def _build_app(session_factory, current_user_id: str, fake_ai: FakeAIService) -> FastAPI:
    """构造仅含 imitation router 的最小 app + 依赖覆盖。

    模仿真实运行时的中间件：把 user_id 注入 request.state。
    """
    app = FastAPI()
    app.include_router(imit_api.router, prefix="/api")

    class _UserMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.user_id = current_user_id
            return await call_next(request)

    app.add_middleware(_UserMiddleware)

    async def _override_get_db():
        sess = session_factory()
        try:
            yield sess
        finally:
            await sess.close()

    def _override_user_ai_service():
        return fake_ai

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_user_ai_service] = _override_user_ai_service
    return app


class TestPreviewApi:
    @pytest.mark.asyncio
    async def test_preview_returns_meta_without_calling_ai(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            await _seed_character(sess, proj.id, "李逸")
            p = await _seed_pack(
                sess, "u-A", task_id="t-1",
                methodology={"prompt_content": "金手指设计"},
                style={"prompt_content": "白描节奏"},
            )
            await _attach(sess, proj.id, p.id, dims=["methodology", "style"])
            await sess.commit()

        fake = FakeAIService(["X"])  # 不会被调用
        app = _build_app(session_factory, "u-A", fake)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/imitate-chapter-preview",
                json={"user_intent": "主角觉醒"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "金手指设计" in data["user_prompt"]
            assert "白描节奏" in data["system_prompt"]
            assert data["target_word_count"] == 2000
            assert data["strength"] in ("light", "medium", "deep")
            assert set(data["used_dimensions"]) >= {"methodology", "style"}
            # AI 服务未被调用
            assert fake.last_prompt is None

    @pytest.mark.asyncio
    async def test_preview_404_for_other_user(self, session_factory):
        async with session_factory() as sess:
            await _seed_project(sess, "u-B")  # 项目属于 B
            await sess.commit()

        app = _build_app(session_factory, "u-A", FakeAIService([]))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/imitate-chapter-preview",
                json={"user_intent": "x"},
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_422_when_no_attachment(self, session_factory):
        async with session_factory() as sess:
            await _seed_project(sess, "u-A")
            await sess.commit()

        app = _build_app(session_factory, "u-A", FakeAIService([]))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/imitate-chapter-preview",
                json={"user_intent": "x"},
            )
            assert resp.status_code == 422
            assert "未挂载" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_preview_422_when_explicit_pack_not_attached(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p_other = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "s"})
            # 不挂载！
            await sess.commit()
            pack_id_unmounted = p_other.id

        app = _build_app(session_factory, "u-A", FakeAIService([]))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/imitate-chapter-preview",
                json={"user_intent": "x", "pack_ids": [pack_id_unmounted]},
            )
            assert resp.status_code == 422


class TestStreamApi:
    @pytest.mark.asyncio
    async def test_stream_emits_meta_content_done(self, session_factory):
        async with session_factory() as sess:
            proj = await _seed_project(sess, "u-A")
            p = await _seed_pack(sess, "u-A", task_id="t-1", style={"prompt_content": "S"})
            await _attach(sess, proj.id, p.id, dims=["style"])
            await sess.commit()

        fake = FakeAIService(["你好", "，世界。"])
        app = _build_app(session_factory, "u-A", fake)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/projects/proj-1/imitate-chapter-stream",
                json={"user_intent": "x", "target_word_count": 500},
            ) as resp:
                assert resp.status_code == 200
                chunks: List[str] = []
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        chunks.append(line[5:].strip())

        # 至少包含 progress / meta / content / done
        events = [json.loads(c) for c in chunks if c]
        types = [e.get("type") for e in events]
        assert "progress" in types
        assert "meta" in types
        assert "content" in types
        assert "done" in types

        # meta 信息正确
        meta = next(e for e in events if e.get("type") == "meta")
        assert "style" in meta["used_dimensions"]
        assert meta["used_packs"][0]["source_book_title"] == "原书.txt"

        # content 拼起来 = AI 输出
        content = "".join(e["content"] for e in events if e.get("type") == "content")
        assert content == "你好，世界。"

        # AI service 被调用，且 system 含 style 内容
        assert fake.last_prompt is not None
        assert "S" in (fake.last_system or "")

    @pytest.mark.asyncio
    async def test_stream_emits_error_on_no_attachment(self, session_factory):
        async with session_factory() as sess:
            await _seed_project(sess, "u-A")
            await sess.commit()

        fake = FakeAIService(["should_not_be_emitted"])
        app = _build_app(session_factory, "u-A", fake)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/projects/proj-1/imitate-chapter-stream",
                json={"user_intent": "x"},
            ) as resp:
                assert resp.status_code == 200  # SSE 永远 200
                events = []
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        events.append(json.loads(line[5:].strip()))

        types = [e.get("type") for e in events]
        assert "error" in types
        # AI 流未被消费
        assert fake.last_prompt is None
        # done 不应在 error 之后再出现
        assert types[-1] == "error"

    @pytest.mark.asyncio
    async def test_stream_404_for_other_user(self, session_factory):
        async with session_factory() as sess:
            await _seed_project(sess, "u-B")
            await sess.commit()

        app = _build_app(session_factory, "u-A", FakeAIService([]))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/projects/proj-1/imitate-chapter-stream",
                json={"user_intent": "x"},
            )
            assert resp.status_code == 404
