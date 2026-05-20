"""V4 Phase 3 manual E2E: 装配一个真实的章节生成 prompt（不调 LLM）。

用法：
    cd backend
    python -m tests.manual.test_e2e_assemble

前提：
- backend/data/mumuai.db 中至少有一个 ready 状态的 ReferencePack
- 自动创建测试项目 + 章纲 + 挂载关系，运行后会留在 DB 里供人工 review

目的：
- 验证 PromptAssembler 在真实拆书数据上能跑通装配
- 对比 S/M/L/XL 4 档位的 prompt 差异
- 给人工 review 实际装配出的 prompt 看是否合理
"""
from __future__ import annotations

import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_engine
from app.models.chapter_outline import ChapterOutline
from app.models.project import Project
from app.models.project_reference_pack import ProjectReferencePack
from app.models.reference_pack import ReferencePack
from app.services.reference_pack import AssemblyContext, PromptAssembler


TEST_PROJECT_ID = "_e2e_test_project_001"
TEST_CHAPTER_OUTLINE_ID = "_e2e_test_chapter_outline_001"


async def _setup_test_data(db: AsyncSession, pack_id: str) -> None:
    """幂等地创建/重置测试项目 + 章纲 + 挂载。"""
    # 清理旧测试数据
    await db.execute(
        delete(ChapterOutline).where(ChapterOutline.id == TEST_CHAPTER_OUTLINE_ID)
    )
    await db.execute(
        delete(ProjectReferencePack).where(
            ProjectReferencePack.project_id == TEST_PROJECT_ID
        )
    )
    await db.execute(delete(Project).where(Project.id == TEST_PROJECT_ID))
    await db.commit()

    project = Project(
        id=TEST_PROJECT_ID,
        user_id="_test_user",
        title="测试项目：修真俗人",
        theme="废物逆袭",
        genre="修仙",
        narrative_perspective="第三人称",
        world_time_period="架空古代修真世界",
        world_location="东陆青木镇",
        world_atmosphere="表面市井烟火，暗藏修真势力",
        world_rules="灵丹需对应灵根、九转灵心丹专克心脉损伤",
        description="一个废柴剑修隐藏身份在市井中行医救人的故事",
    )
    db.add(project)

    co = ChapterOutline(
        id=TEST_CHAPTER_OUTLINE_ID,
        project_id=TEST_PROJECT_ID,
        chapter_number=17,
        title="药铺奇遇",
        scene="青木镇药铺",
        pov="林青云",
        plot_points="主角去药铺求购九转灵心丹，被老药师拒绝；老药师私下苦于祖传炼丹术失传",
        key_events='["主角和发小吃早饭", "路上聊起老药师", "到达药铺", "被老药师拒绝"]',
        characters_involved='["林青云", "王二虎", "老药师"]',
        target_word_count=3000,
        bridge_position="intro",
    )
    db.add(co)

    prp = ProjectReferencePack(
        project_id=TEST_PROJECT_ID,
        pack_id=pack_id,
        default_dimensions='["methodology","style","structure","archetypes","worldbuilding"]',
        default_strength="medium",
    )
    db.add(prp)
    await db.commit()


def _make_test_ctx(model_name: str) -> AssemblyContext:
    return AssemblyContext(
        scene="chapter_content",
        model_name=model_name,
        project_id=TEST_PROJECT_ID,
        chapter_outline_id=TEST_CHAPTER_OUTLINE_ID,
        target_word_count=3000,
        bridge_position="intro",
        bridge_context={
            "title": "拜师求药",
            "goal": "求老药师炼制九转灵心丹",
            "showoff_point": "用现代医学知识识破老药师故意刁难的假药方",
            "next_bridge_goal": "去拜访云鹿书院大儒",
        },
    )


async def run() -> None:
    engine = await get_engine("e2e_test")
    AS = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AS() as db:
        rp = (await db.execute(select(ReferencePack))).scalar_one_or_none()
        if not rp:
            print("[E2E] 错误：没有 ReferencePack。请先完成一次拆书。")
            return

        print(f"[E2E] 使用 ReferencePack: {rp.source_book_title}")
        print(f"[E2E] generated_dimensions: {rp.generated_dimensions}\n")

        await _setup_test_data(db, rp.id)
        print("[E2E] 测试项目 + 章纲 + 挂载关系已创建\n")

        assembler = PromptAssembler()
        results = {}
        for model_name in ("qwen-plus", "qwen-max", "deepseek-v3", "claude-sonnet-4-5"):
            ctx = _make_test_ctx(model_name)
            prompt = await assembler.assemble(db, ctx)
            results[model_name] = prompt

        # 对比表
        print("=" * 75)
        print(f"{'模型':<22} {'档位':>4} {'填充':>4} {'跳过':>4} {'截断':>4} "
              f"{'sys':>6} {'user':>6} {'≈tok':>6}")
        print("-" * 75)
        for model, p in results.items():
            print(f"{model:<22} {p.model_tier:>4} {len(p.slots_filled):>4} "
                  f"{len(p.slots_skipped):>4} {len(p.slots_truncated):>4} "
                  f"{len(p.system_prompt):>6} {len(p.user_prompt):>6} "
                  f"{p.actual_tokens_estimate:>6}")
        print("=" * 75)

        # 详细展示 deepseek-v3 装配的完整 prompt
        prompt = results["deepseek-v3"]
        print(f"\n\n>>>>>>> deepseek-v3 (tier={prompt.model_tier}) 完整 prompt <<<<<<<\n")
        print("### SYSTEM PROMPT ###")
        print(prompt.system_prompt)
        print("\n### USER PROMPT ###")
        print(prompt.user_prompt)


if __name__ == "__main__":
    asyncio.run(run())
