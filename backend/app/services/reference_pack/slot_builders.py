"""V4.3 槽位 builder 函数（Phase 1 骨架版本）。

每个 builder 接收 (db, ctx) → 返回该槽位的字符串内容（或空字符串表示跳过）。

设计原则：
- builder 函数纯异步、纯查表/纯字符串拼接，不调用 LLM
- 失败时返回空字符串（被 assembler 标 skipped）
- required 槽位空返回 → assembler 抛 ValueError
- 拆书 builder（dissect_*）直接 SELECT ReferencePack 预压缩字段（V4.4 K5 三档）

Phase 1 骨架版本：
- 业务必填槽位（system_role / chapter_outline / project_skeleton / output_spec）实现最小可用版
- 拆书槽位实现 SELECT 预压缩字段的查询逻辑
- 历史接续/记忆/桥段位置等先返回基础占位，留 TODO 给后续完善
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================
# system 段 builder
# ============================================================

async def build_system_role(db: AsyncSession, ctx: Any) -> str:
    """系统角色定位（全局静态，可缓存）。"""
    genre = (ctx.genre or "网文").strip()
    return (
        f"你是一位专业的小说作家，擅长创作{genre}类型作品。\n"
        "你必须严格遵守用户给出的所有创作约束。"
    )


async def build_system_base_style(db: AsyncSession, ctx: Any) -> str:
    """基础叙事原则（全局静态，跨项目复用，可缓存）。"""
    perspective = ctx.narrative_perspective or "第三人称"
    return f"""**基础叙事原则：**
- 必须使用{perspective}视角稳稳讲故事
- 多用短句（10-25 字）
- 像普通人讲故事，避免文学化、文学散文化
- ❌ 禁止"道心坚定"、"一往无前"、"天地本质" 等套路语
- ❌ 禁止用"为了天下苍生"、"更大的使命"等宏大主题
- ❌ 禁止排比句式总结主角心理
- ✅ 结尾用具体动作、对话或场景描写
- ✅ 心理描写以身体感受为主（发热、出汗、心跳）"""


async def build_dissect_style(db: AsyncSession, ctx: Any) -> str:
    """拆书文风指令（项目级缓存）。

    实现：SELECT 项目挂载的第一个 ReferencePack 的 style_<strength> 字段。
    """
    pack = await _get_first_attached_pack(db, ctx.project_id)
    if not pack:
        return ""
    strength = _get_strength_for(ctx, "style")
    text = pack.get_precompressed("style", strength)
    if not text:
        return ""
    book_title = getattr(pack, "source_book_title", "") or ""
    return f"**拆书参考文风（来源：《{book_title}》）：**\n{text}"


# ============================================================
# user 段 业务 builder
# ============================================================

async def build_project_skeleton(db: AsyncSession, ctx: Any) -> str:
    """项目基本信息（项目级缓存）。"""
    from app.models.project import Project

    result = await db.execute(select(Project).where(Project.id == ctx.project_id))
    project = result.scalar_one_or_none()
    if not project:
        # 兜底：用 ctx 中的元数据
        title = ctx.title or "未命名"
        return f"【项目信息】\n书名：{title}"

    lines = [
        "【项目信息】",
        f"书名：{project.title or ctx.title or '未命名'}",
        f"主题：{project.theme or ctx.theme or '未设定'}",
        f"类型：{project.genre or ctx.genre or '网文'}",
        f"视角：{project.narrative_perspective or ctx.narrative_perspective or '第三人称'}",
        "",
        "【世界观】",
        f"时间：{project.world_time_period or '未设定'}",
        f"地点：{project.world_location or '未设定'}",
        f"氛围：{project.world_atmosphere or '未设定'}",
    ]
    if project.world_rules:
        lines.append(f"规则：{project.world_rules[:300]}")
    return "\n".join(lines)


async def build_chapter_outline(db: AsyncSession, ctx: Any) -> str:
    """本章信息（章节级动态，不缓存）。"""
    if not ctx.chapter_outline_id:
        return ""
    from app.models.chapter_outline import ChapterOutline

    result = await db.execute(
        select(ChapterOutline).where(ChapterOutline.id == ctx.chapter_outline_id)
    )
    co = result.scalar_one_or_none()
    if not co:
        return ""

    lines = [
        f"第{co.chapter_number}章：{co.title}",
    ]
    if co.scene:
        lines.append(f"- 场景：{co.scene}")
    if co.pov:
        lines.append(f"- 视角：{co.pov}")
    if co.plot_points:
        lines.append(f"- 剧情要点：{co.plot_points}")
    if co.key_events:
        lines.append(f"- 关键事件：{co.key_events}")
    if co.characters_involved:
        lines.append(f"- 涉及角色：{co.characters_involved}")
    lines.append(f"- 目标字数：{ctx.target_word_count}")
    return "\n".join(lines)


async def build_bridge_position(db: AsyncSession, ctx: Any) -> str:
    """K2 桥段位置约束（章节级，不缓存）。

    Phase 1 骨架：返回基础约束模板。完整 4 套 prompt 模板留 Phase 2 P2-3 补全。
    """
    if not ctx.bridge_position or not ctx.bridge_context:
        return ""

    pos = ctx.bridge_position
    bridge_title = ctx.bridge_context.get("title", "未命名桥段")
    bridge_goal = ctx.bridge_context.get("goal", "")
    showoff = ctx.bridge_context.get("showoff_point", "")

    POSITION_NAMES = {
        "intro": "C1 代入+信息差（5:5）",
        "build": "C2 拉扯+开装（9:1）",
        "payoff": "C3 兑现爽点（无钩子）",
        "aftermath": "C4 善后+下一目标",
    }
    pos_name = POSITION_NAMES.get(pos, pos)

    return f"""本章 = 桥段「{bridge_title}」 {pos_name}
- 桥段目标：{bridge_goal}
- 桥段装逼点：{showoff}

【V4.3 骨架版本，完整 4 套位置约束模板见 Phase 2 P2-3】"""


async def build_history_full(db: AsyncSession, ctx: Any) -> str:
    """最近 N 章的完整摘要（按 HISTORICAL_CONTEXT_TABLE.full_count）。

    Phase 1 骨架：先返回空（等 V4.4 P2 Chapter summary_full 字段就绪后补全）。
    """
    return ""


async def build_history_normal(db: AsyncSession, ctx: Any) -> str:
    """中段章节摘要。Phase 1 骨架版返回空。"""
    return ""


async def build_history_brief(db: AsyncSession, ctx: Any) -> str:
    """早段章节摘要。Phase 1 骨架版返回空。"""
    return ""


async def build_memory_topk(db: AsyncSession, ctx: Any) -> str:
    """智能记忆 top-K（依赖现有 memory_service）。

    Phase 1 骨架：先返回空，待整合现有 MemoryService.search_memories。
    """
    return ""


async def build_output_spec(db: AsyncSession, ctx: Any) -> str:
    """输出要求（章节级，但内容稳定）。"""
    if ctx.scene == "chapter_content":
        word_count = ctx.target_word_count or 3000
        soft_low = int(word_count * 0.9)
        soft_high = int(word_count * 1.1)
        return (
            f"请直接输出正文，不要章节标题。\n"
            f"目标字数：{word_count}（允许范围 {soft_low}-{soft_high}）"
        )
    return "请按 JSON 格式输出结果，不要任何 markdown 标记。"


# ============================================================
# 拆书 user 段 builder（统一查 ReferencePack 预压缩字段）
# ============================================================

def _make_dissect_builder(dimension: str) -> Callable[[AsyncSession, Any], Awaitable[str]]:
    """工厂：生成读取指定维度预压缩字段的 builder。"""
    async def _builder(db: AsyncSession, ctx: Any) -> str:
        pack = await _get_first_attached_pack(db, ctx.project_id)
        if not pack:
            return ""
        strength = _get_strength_for(ctx, dimension)
        text = pack.get_precompressed(dimension, strength)
        return text or ""
    _builder.__name__ = f"build_dissect_{dimension}"
    return _builder


build_dissect_methodology = _make_dissect_builder("methodology")
build_dissect_structure = _make_dissect_builder("structure")
build_dissect_archetypes = _make_dissect_builder("archetypes")
build_dissect_worldbuilding = _make_dissect_builder("worldbuilding")
build_dissect_synopsis = _make_dissect_builder("synopsis")
build_dissect_bridges = _make_dissect_builder("bridges")
build_dissect_char_arch = _make_dissect_builder("character_archive")


async def build_dissect_corpus(db: AsyncSession, ctx: Any) -> str:
    """corpus 走 BM25 动态检索（不读预压缩）。

    Phase 1 骨架：先返回空。
    完整版（V4.4 K6 P2 Contextual Retrieval）会调 HybridCorpusRetriever。
    """
    return ""


# ============================================================
# helpers
# ============================================================

async def _get_first_attached_pack(db: AsyncSession, project_id: str):
    """SELECT 项目挂载的第一个 ReferencePack（按 attached_at 排序）。"""
    if not project_id:
        return None
    try:
        from app.models.reference_pack import ReferencePack
        from app.models.project_reference_pack import ProjectReferencePack
    except ImportError:
        return None

    result = await db.execute(
        select(ReferencePack)
        .join(ProjectReferencePack, ProjectReferencePack.pack_id == ReferencePack.id)
        .where(ProjectReferencePack.project_id == project_id)
        .order_by(ProjectReferencePack.attached_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _get_strength_for(ctx: Any, dimension: str) -> str:
    """查 (scene, tier) → policy → strength。"""
    from app.services.reference_pack.policy_tables import get_policy
    policy = get_policy(ctx.scene, ctx.model_name)
    return policy.get(dimension, "off")


# ============================================================
# builder 注册表（assembler 按 slot.name 查找）
# ============================================================

SLOT_BUILDERS: dict[str, Callable[[AsyncSession, Any], Awaitable[str]]] = {
    # system 段
    "system_role":            build_system_role,
    "system_base_style":      build_system_base_style,
    "dissect_style":          build_dissect_style,
    # user 段 - 必填业务
    "project_skeleton":       build_project_skeleton,
    "chapter_outline":        build_chapter_outline,
    "output_spec":            build_output_spec,
    # user 段 - 业务
    "bridge_position":        build_bridge_position,
    "history_full":           build_history_full,
    "history_normal":         build_history_normal,
    "history_brief":          build_history_brief,
    "memory_topk":            build_memory_topk,
    # user 段 - 拆书 8 维
    "dissect_methodology":    build_dissect_methodology,
    "dissect_structure":      build_dissect_structure,
    "dissect_archetypes":     build_dissect_archetypes,
    "dissect_worldbuilding":  build_dissect_worldbuilding,
    "dissect_synopsis":       build_dissect_synopsis,
    "dissect_corpus":         build_dissect_corpus,
    "dissect_bridges":        build_dissect_bridges,
    "dissect_character_archive": build_dissect_char_arch,
}
