"""V4.3 PromptAssembler：按 blueprint 装配单遍历填充 + 硬截断（v4_design.md §10.5.1）。

核心原则：
- 唯一的 for 循环遍历 blueprint 槽位
- builder 产出超过 max_tokens → 硬截断
- 零 budget 计算、零 if/else 分支、零 fallback
- 同 (scene, model_name) + 同 ctx = 完全相同的 prompt（可复现）

公开 API：
    async with AsyncSession() as db:
        prompt = await PromptAssembler().assemble(db, AssemblyContext(
            scene='chapter_content',
            model_name='deepseek-v3',
            project_id='...',
            chapter_id='...',
        ))
        # prompt.system_prompt / prompt.user_prompt 可直接发给 AI service
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reference_pack.blueprint import (
    PROMPT_BLUEPRINT,
    Slot,
)
from app.services.reference_pack.policy_tables import (
    get_model_tier,
)
from app.services.reference_pack.slot_builders import SLOT_BUILDERS

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class AssemblyContext:
    """所有生成场景的统一组装上下文。

    业务方根据场景填充必要字段，未用到的字段保持默认值。
    """
    scene: str                                # 必填：'chapter_content' / 'character' / ...
    model_name: str                           # 必填：用于查 model tier
    project_id: str                           # 必填

    # 章节相关（chapter_content / scene_generation / chapter_regenerate）
    chapter_id: Optional[str] = None
    chapter_outline_id: Optional[str] = None
    target_word_count: int = 3000

    # K2 桥段相关（章节生成时按桥段位置注入）
    bridge_position: Optional[str] = None     # 'intro' / 'build' / 'payoff' / 'aftermath'
    bridge_context: Optional[dict[str, Any]] = None

    # 场景生成
    plot_card_id: Optional[str] = None

    # 角色生成
    role_type: Optional[str] = None
    user_input: Optional[str] = None

    # 重生成
    modification_instructions: Optional[str] = None

    # 灵感 / 元数据（不依赖项目，部分场景用）
    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    genre: Optional[str] = None
    narrative_perspective: Optional[str] = None

    # 任意业务字段透传（builder 可按需读取）
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssembledPrompt:
    """组装结果。"""
    system_prompt: str
    user_prompt: str

    # 可选：V4.4 K5 用于注入 cache_control 的多段 blocks
    system_blocks: list[dict[str, Any]] = field(default_factory=list)
    user_blocks: list[dict[str, Any]] = field(default_factory=list)

    # 审计字段
    slots_filled: list[str] = field(default_factory=list)
    slots_truncated: list[str] = field(default_factory=list)
    slots_skipped: list[str] = field(default_factory=list)
    actual_tokens_estimate: int = 0
    scene: str = ""
    model_tier: str = ""


# ============================================================
# 核心 Assembler
# ============================================================

class PromptAssembler:
    """V4.3 极简组装器：按 blueprint 遍历填充 + 截断。"""

    # 中文字符 1 字 ≈ 1.5 token，英文 4 字符 ≈ 1 token
    CN_CHAR_TO_TOKEN = 1.5

    async def assemble(
        self,
        db: AsyncSession,
        ctx: AssemblyContext,
    ) -> AssembledPrompt:
        """主入口：返回 AssembledPrompt。

        Raises:
            ValueError: 未知 scene + model_tier 组合；或 required slot 内容为空
        """
        tier = get_model_tier(ctx.model_name)
        blueprint = PROMPT_BLUEPRINT.get((ctx.scene, tier))
        if blueprint is None:
            raise ValueError(
                f"No blueprint for (scene={ctx.scene!r}, tier={tier!r}); "
                f"register it in SCENE_BUSINESS_TEMPLATES"
            )

        # 唯一的 for 循环
        system_parts: list[str] = []
        user_parts: list[str] = []
        system_blocks: list[dict[str, Any]] = []
        user_blocks: list[dict[str, Any]] = []
        slots_filled: list[str] = []
        slots_truncated: list[str] = []
        slots_skipped: list[str] = []

        for slot in blueprint:
            builder = SLOT_BUILDERS.get(slot.name)
            if builder is None:
                logger.warning(
                    "[Assembler] no builder for slot %r, skip", slot.name
                )
                slots_skipped.append(slot.name)
                continue

            try:
                content = await builder(db, ctx)
            except Exception as exc:
                logger.error(
                    "[Assembler] builder %r failed: %s", slot.name, exc,
                    exc_info=True,
                )
                if slot.required:
                    raise
                slots_skipped.append(slot.name)
                continue

            content = (content or "").strip()
            if not content:
                if slot.required:
                    raise ValueError(
                        f"Required slot {slot.name!r} returned empty content"
                    )
                slots_skipped.append(slot.name)
                continue

            # 加标签前缀
            if slot.label:
                content = f"{slot.label}\n{content}"

            # 硬截断
            truncated = self._truncate(content, slot.max_tokens)
            if len(truncated) < len(content):
                slots_truncated.append(slot.name)

            # 放进对应段
            if slot.section == "system":
                system_parts.append(truncated)
                system_blocks.append(self._make_block(truncated, slot))
            else:
                user_parts.append(truncated)
                user_blocks.append(self._make_block(truncated, slot))

            slots_filled.append(slot.name)

        system_prompt = "\n\n".join(system_parts)
        user_prompt = "\n\n".join(user_parts)
        tokens = self._estimate_tokens(system_prompt + "\n" + user_prompt)

        logger.info(
            "[Assembler] scene=%s tier=%s filled=%d truncated=%d skipped=%d tokens≈%d",
            ctx.scene, tier, len(slots_filled),
            len(slots_truncated), len(slots_skipped), tokens,
        )

        return AssembledPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            system_blocks=system_blocks,
            user_blocks=user_blocks,
            slots_filled=slots_filled,
            slots_truncated=slots_truncated,
            slots_skipped=slots_skipped,
            actual_tokens_estimate=tokens,
            scene=ctx.scene,
            model_tier=tier,
        )

    # ---------------- internal helpers ----------------

    @classmethod
    def _truncate(cls, text: str, max_tokens: int) -> str:
        """硬截断到 max_tokens（中文字符估算）。"""
        if max_tokens <= 0:
            return ""
        max_chars = int(max_tokens / cls.CN_CHAR_TO_TOKEN)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "…(截断)"

    @classmethod
    def _estimate_tokens(cls, text: str) -> int:
        """粗估 token 数（中文 1 字 ≈ 1.5 token，其他 4 字符 ≈ 1 token）。"""
        if not text:
            return 0
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * cls.CN_CHAR_TO_TOKEN + other_chars / 4)

    @staticmethod
    def _make_block(text: str, slot: Slot) -> dict[str, Any]:
        """构造 V4.4 K5 风格的 block（含 cache_control 标记）。

        Provider 适配层会按 model_name 决定是否真的传 cache_control 给 API。
        """
        block: dict[str, Any] = {"type": "text", "text": text}
        if slot.cacheable and slot.cache_tier in ("global", "project"):
            # Anthropic 风格 cache_control
            block["cache_control"] = {"type": "ephemeral"}
        return block
