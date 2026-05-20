"""V3 R5 一键仿写服务

职责（仿写专用上层）：
1. 加载 [项目状态 + 作者意图 + 已挂载/勾选的参考包] 三类输入
2. 拼装 system_prompt + user_prompt（文风注入 system，结构/方法论/角色塑造/世界观/语料注入 user）
3. 提供同步 preview（dry-run）与 SSE 流式生成两种入口

参考资料组装能力（强度档位 / 维度过滤 / 5 维 + corpus 拼装）已抽到 ``reference_pack_injector``，
本模块通过 ``self.injector`` 委托复用，避免与其他生成场景双源维护。

对外 API（向下兼容）：
- ``ImitationService.resolve_packs / resolve_dimensions / resolve_strength``：代理给 injector
- ``ImitationService.assemble_prompt`` / ``stream_imitation``：仿写主入口
- 本模块顶层 ``StrengthProfile`` / ``_ResolvedPack`` 仍可 import（re-export 自 injector）

参见：
- 设计文档：@/agent-docs/features/book_dissect_v3_imitation_design.md §5
- R2 抽取设计：@/agent-docs/features/dissect_to_creation_pipeline.md §4
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import get_logger
from app.models.chapter import Chapter
from app.models.chapter_outline import ChapterOutline
from app.models.character import Character
from app.models.project import Project
from app.services.ai_service import AIService
# 重新导出：测试与下游代码继续从本模块 import 这些符号
from app.services.reference_pack_injector import (  # noqa: F401  re-export
    ReferenceBlock,
    ReferencePackInjector,
    StrengthProfile,
    _ResolvedPack,
    _dedup_keep_order,
    _safe_json,
    _serialize_dimension,
    _serialize_style,
    _truncate,
)

logger = get_logger(__name__)


# ============================================================
# 数据载体（仿写专用：项目当前状态快照）
# ============================================================


@dataclass
class _ProjectContext:
    """项目当前状态快照（轻量；不含 RAG 历史）。"""

    project: Project
    main_characters: List[Character] = field(default_factory=list)
    target_chapter: Optional[Chapter] = None
    target_outline: Optional[ChapterOutline] = None
    recent_chapters: List[Chapter] = field(default_factory=list)


# ============================================================
# 主服务类
# ============================================================


class ImitationService:
    """一键仿写：依赖注入 AIService（来自 get_user_ai_service）。"""

    # 类常量便于测试 monkeypatch
    DEFAULT_DIMENSION_FALLBACK: tuple[str, ...] = ("methodology", "style", "corpus")
    RECENT_CHAPTERS_FOR_CONTEXT: int = 3
    RECENT_CHAPTER_CHARS_TRUNCATE: int = 1500
    MAIN_CHARACTERS_LIMIT: int = 6

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        # 参考资料组装统一委托给 injector（R2 抽出，跨场景共享）
        self.injector = ReferencePackInjector(ai_service)

    # ----------------------------------------------------------------
    # 输入归一化：代理给 injector（保留方法签名以兼容下游调用）
    # ----------------------------------------------------------------

    async def resolve_packs(
        self,
        db: AsyncSession,
        project_id: str,
        pack_ids: Optional[List[str]],
    ) -> List[_ResolvedPack]:
        return await self.injector.resolve_packs(db, project_id, pack_ids)

    def resolve_dimensions(
        self,
        packs: List[_ResolvedPack],
        explicit: Optional[List[str]],
    ) -> List[str]:
        return self.injector.resolve_dimensions(
            packs, explicit, fallback=self.DEFAULT_DIMENSION_FALLBACK
        )

    def resolve_strength(
        self,
        packs: List[_ResolvedPack],
        explicit: Optional[str],
    ) -> str:
        return self.injector.resolve_strength(packs, explicit)

    # ----------------------------------------------------------------
    # 项目上下文加载（轻量）
    # ----------------------------------------------------------------

    async def load_project_context(
        self,
        db: AsyncSession,
        project_id: str,
        target_chapter_id: Optional[str],
    ) -> _ProjectContext:
        """加载项目快照：项目本体 + 主角 + 当前章节大纲 + 最近 3 章（裁剪）。

        刻意避开 build_smart_chapter_context 的向量库依赖：
        - 测试场景下不需要 memory_service
        - R5 V1 只取最近章节，足够 LLM 维持人物设定 / 风格延续
        """
        proj_result = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在：{project_id}")

        # 主角（role_type=protagonist 优先；不足时补 supporting）
        char_result = await db.execute(
            select(Character)
            .where(Character.project_id == project_id)
            .where(Character.is_organization.is_(False))
        )
        all_chars = list(char_result.scalars().all())
        # 排序：protagonist > major > supporting > minor > 其他
        rank = {"protagonist": 0, "major": 1, "supporting": 2, "minor": 3}
        all_chars.sort(key=lambda c: rank.get((c.role_type or "minor").lower(), 99))
        main_chars = all_chars[: self.MAIN_CHARACTERS_LIMIT]

        target_chapter: Optional[Chapter] = None
        target_outline: Optional[ChapterOutline] = None
        recent_chapters: List[Chapter] = []

        if target_chapter_id:
            ch_result = await db.execute(
                select(Chapter).where(Chapter.id == target_chapter_id)
            )
            target_chapter = ch_result.scalar_one_or_none()
            if target_chapter and target_chapter.project_id != project_id:
                # 安全护栏：API 层应已校验，这里再兜一道
                raise ValueError("目标章节不属于当前项目")
            if target_chapter and target_chapter.chapter_outline_id:
                ol_result = await db.execute(
                    select(ChapterOutline).where(
                        ChapterOutline.id == target_chapter.chapter_outline_id
                    )
                )
                target_outline = ol_result.scalar_one_or_none()

        # 最近 N 章：以 target_chapter.chapter_number 为锚；无锚则取最大序号往前数
        if target_chapter:
            anchor = target_chapter.chapter_number
            recent_q = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .where(Chapter.chapter_number < anchor)
                .where(Chapter.content.isnot(None))
                .where(Chapter.content != "")
                .order_by(Chapter.chapter_number.desc())
                .limit(self.RECENT_CHAPTERS_FOR_CONTEXT)
            )
        else:
            recent_q = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .where(Chapter.content.isnot(None))
                .where(Chapter.content != "")
                .order_by(Chapter.chapter_number.desc())
                .limit(self.RECENT_CHAPTERS_FOR_CONTEXT)
            )
        recent_result = await db.execute(recent_q)
        recent_chapters = list(reversed(recent_result.scalars().all()))  # 升序

        return _ProjectContext(
            project=project,
            main_characters=main_chars,
            target_chapter=target_chapter,
            target_outline=target_outline,
            recent_chapters=recent_chapters,
        )

    # ----------------------------------------------------------------
    # Prompt 拼装
    # ----------------------------------------------------------------

    def _format_project_state(self, ctx: _ProjectContext) -> str:
        """[项目当前状态] 区块，自然语言描述。"""
        proj = ctx.project
        lines: List[str] = []
        lines.append(f"小说标题：《{proj.title}》")
        if proj.theme:
            lines.append(f"主题：{proj.theme}")
        if proj.genre:
            lines.append(f"题材：{proj.genre}")
        if proj.narrative_perspective:
            lines.append(f"叙事视角：{proj.narrative_perspective}")
        world_bits = []
        if proj.world_time_period:
            world_bits.append(f"时代：{proj.world_time_period}")
        if proj.world_location:
            world_bits.append(f"地点：{proj.world_location}")
        if proj.world_atmosphere:
            world_bits.append(f"氛围：{proj.world_atmosphere}")
        if world_bits:
            lines.append("世界观：" + "；".join(world_bits))
        if proj.world_rules:
            rules_short = _truncate(proj.world_rules, 600)
            lines.append(f"世界规则：{rules_short}")

        # 主角
        if ctx.main_characters:
            char_lines = ["主要角色（用户已设定，仿写时必须遵守这些角色身份/性格）："]
            for c in ctx.main_characters:
                bits = [c.name]
                if c.role_type:
                    bits.append(f"({c.role_type})")
                detail = []
                if c.gender:
                    detail.append(c.gender)
                if c.age:
                    detail.append(c.age)
                if c.personality:
                    detail.append(_truncate(c.personality, 80))
                if detail:
                    bits.append("，" + "/".join(detail))
                char_lines.append("- " + "".join(bits))
            lines.append("\n".join(char_lines))

        # 当前章节大纲
        if ctx.target_chapter:
            ch = ctx.target_chapter
            lines.append(f"\n本次仿写目标章节：第{ch.chapter_number}章《{ch.title}》")
            outline_text = ""
            if ctx.target_outline:
                outline_text = (
                    ctx.target_outline.plot_points
                    or ctx.target_outline.summary
                    or ""
                )
            elif ch.summary:
                outline_text = ch.summary
            if outline_text:
                lines.append(f"章纲：{_truncate(outline_text, 1000)}")

        # 最近 3 章节选
        if ctx.recent_chapters:
            recent_lines = ["最近章节（截选）："]
            for ch in ctx.recent_chapters:
                content = _truncate(
                    ch.content or "", self.RECENT_CHAPTER_CHARS_TRUNCATE
                )
                recent_lines.append(
                    f"--- 第{ch.chapter_number}章《{ch.title}》 ---\n{content}"
                )
            lines.append("\n".join(recent_lines))

        return "\n\n".join(lines)

    def _format_user_intent(self, user_intent: str) -> str:
        return f"[作者本次创作意图]\n{user_intent.strip()}"

    # ----------------------------------------------------------------
    # 对外：拼装 / 流式
    # ----------------------------------------------------------------

    async def assemble_prompt(
        self,
        db: AsyncSession,
        project_id: str,
        *,
        user_intent: str,
        target_chapter_id: Optional[str],
        pack_ids: Optional[List[str]],
        dimensions: Optional[List[str]],
        strength: Optional[str],
        target_word_count: int,
        style_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """拼装完整 prompt 并返回元数据（供 API 层包装为响应或喂给 AIService）。

        Returns:
            {
              "system_prompt": str,
              "user_prompt": str,
              "used_packs": List[{pack_id, source_book_title, dimensions: [...]}],
              "used_dimensions": List[str],
              "strength": str,
              "target_word_count": int,
              "project_context_chars": int,
              "reference_chars": int,
            }
        """
        packs = await self.resolve_packs(db, project_id, pack_ids)
        used_dimensions = self.resolve_dimensions(packs, dimensions)
        used_strength = self.resolve_strength(packs, strength)
        profile = StrengthProfile.for_strength(used_strength)

        ctx = await self.load_project_context(db, project_id, target_chapter_id)

        # ====== System Prompt ======
        base_system = (
            "你是一位专业的中文小说写手。你将基于 [作者本次创作意图] 完成一段章节草稿。\n"
            "硬性纪律：\n"
            "1) 严格遵守 [项目当前状态] 中给出的角色身份/性格/世界观/章纲，不得随意改动\n"
            "2) [参考方法论/结构手法/角色塑造/世界观/原书案例] 仅作『如何写』的方法参考，"
            "禁止照抄原书的具体人名/地名/情节/台词\n"
            "3) 输出体感：保持中文小说叙事节奏，避免分点列举式\n"
            "4) 字数控制：在目标字数 ±15% 区间内，结构完整\n"
            "5) 仅输出小说正文，不要输出任何解释、标题、章节号、Markdown 标记或元注释"
        )
        if "style" in used_dimensions:
            style_block = self.injector._format_style_system_prompt(packs, profile)
            if style_block:
                base_system = (
                    base_system + "\n\n[文风参考（影响语气/句式而非具体内容）]\n" + style_block
                )

        # 项目内已有的写作风格叠加（与参考包文风互不冲突，叠加在更后面优先级更高）
        if style_id:
            try:
                from app.services.prompt_service import WritingStyleManager
                from app.models.writing_style import WritingStyle

                ws_result = await db.execute(
                    select(WritingStyle).where(WritingStyle.id == style_id)
                )
                ws = ws_result.scalar_one_or_none()
                if ws and ws.prompt_content:
                    # WritingStyleManager.apply_style_to_prompt 是面向 user prompt 的；
                    # 这里直接把内容追加到 system 末尾，行为与"更高优先级风格"一致
                    base_system = (
                        base_system
                        + "\n\n[项目内自定义文风（优先级最高）]\n"
                        + ws.prompt_content
                    )
            except Exception as e:  # pragma: no cover - 防御性兜底
                logger.warning("[V3-R5] 项目文风加载失败，已忽略：%s", e)

        # ====== User Prompt ======
        ref_sections: List[str] = []
        if "methodology" in used_dimensions:
            s = self.injector._format_methodology(packs, profile)
            if s:
                ref_sections.append(s)
        if "structure" in used_dimensions:
            s = self.injector._format_structure(packs, profile)
            if s:
                ref_sections.append(s)
        if "archetypes" in used_dimensions:
            s = self.injector._format_archetypes(packs, profile)
            if s:
                ref_sections.append(s)
        if "worldbuilding" in used_dimensions:
            s = self.injector._format_worldbuilding(packs, profile)
            if s:
                ref_sections.append(s)
        if "corpus" in used_dimensions:
            s = await self.injector._format_corpus(db, packs, user_intent, profile)
            if s:
                ref_sections.append(s)

        project_state = self._format_project_state(ctx)
        intent_block = self._format_user_intent(user_intent)
        word_block = (
            f"[字数要求]\n请输出约 {target_word_count} 字的小说正文（允许 ±15%）。"
        )

        user_prompt_parts = [
            "[项目当前状态]",
            project_state,
            intent_block,
        ]
        if ref_sections:
            user_prompt_parts.extend(ref_sections)
        user_prompt_parts.append(word_block)
        user_prompt_parts.append(
            "请直接输出小说正文（不要任何前言/标题/分隔线/解释）："
        )
        user_prompt = "\n\n".join(user_prompt_parts)

        # 元数据
        used_packs_meta = []
        for p in packs:
            # 该 pack 在本次实际生效的维度 = 维度并集 ∩ 该 pack 提供的维度
            pack_dims: List[str] = []
            for d in used_dimensions:
                if d == "corpus":
                    pack_dims.append("corpus")  # 由 V2 表提供
                elif d == "style" and p.style:
                    pack_dims.append("style")
                elif d == "methodology" and p.methodology:
                    pack_dims.append("methodology")
                elif d == "structure" and p.structure:
                    pack_dims.append("structure")
                elif d == "archetypes" and p.archetypes:
                    pack_dims.append("archetypes")
                elif d == "worldbuilding" and p.worldbuilding:
                    pack_dims.append("worldbuilding")
            used_packs_meta.append(
                {
                    "pack_id": p.pack_id,
                    "source_book_title": p.source_book_title,
                    "dimensions": _dedup_keep_order(pack_dims),
                }
            )

        return {
            "system_prompt": base_system,
            "user_prompt": user_prompt,
            "used_packs": used_packs_meta,
            "used_dimensions": used_dimensions,
            "strength": used_strength,
            "target_word_count": target_word_count,
            "project_context_chars": len(project_state),
            "reference_chars": sum(len(s) for s in ref_sections),
        }

    async def stream_imitation(
        self,
        db: AsyncSession,
        project_id: str,
        *,
        user_intent: str,
        target_chapter_id: Optional[str],
        pack_ids: Optional[List[str]],
        dimensions: Optional[List[str]],
        strength: Optional[str],
        target_word_count: int,
        style_id: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成：直接 yield 文本片段（API 层包成 SSE）。"""
        bundle = await self.assemble_prompt(
            db,
            project_id,
            user_intent=user_intent,
            target_chapter_id=target_chapter_id,
            pack_ids=pack_ids,
            dimensions=dimensions,
            strength=strength,
            target_word_count=target_word_count,
            style_id=style_id,
        )
        logger.info(
            "[V3-R5] 仿写开始 project=%s strength=%s dims=%s ctx=%d ref=%d",
            project_id,
            bundle["strength"],
            bundle["used_dimensions"],
            bundle["project_context_chars"],
            bundle["reference_chars"],
        )
        async for chunk in self.ai_service.generate_text_stream(
            prompt=bundle["user_prompt"],
            system_prompt=bundle["system_prompt"],
            provider=provider,
            model=model,
        ):
            yield chunk


# ============================================================
# 工具函数（V3.1.3 前的 token 工具；其他通用工具已搬到 reference_pack_injector）
# ============================================================


_STOPWORDS = {
    "的", "了", "和", "与", "及", "以", "但是", "因为", "所以", "如果", "可以",
    "需要", "一个", "一些", "我们", "他们", "她们", "这个", "那个",
    "the", "a", "an", "of", "and", "or", "to", "in", "is", "for", "on",
}


def _tokenize_keywords(text: str) -> List[str]:
    """轻量中文分词：按 2-4 字 n-gram 切片 + 英文单词。"""
    if not text:
        return []
    out: List[str] = []
    # 英文/数字单词
    out.extend(re.findall(r"[A-Za-z0-9]+", text))
    # 中文按 2-gram 取片段（足够覆盖关键词命中）
    cn = re.findall(r"[\u4e00-\u9fff]+", text)
    for seg in cn:
        if len(seg) < 2:
            continue
        for i in range(len(seg) - 1):
            tok = seg[i : i + 2]
            out.append(tok)
    out = [w.lower() for w in out if w.lower() not in _STOPWORDS]
    return _dedup_keep_order(out)


def _score_text(text: str, keywords: List[str]) -> int:
    if not text or not keywords:
        return 0
    low = text.lower()
    return sum(1 for k in keywords if k and k in low)
