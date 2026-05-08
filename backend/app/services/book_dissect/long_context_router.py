"""拆书 V3.1: 长上下文兜底路由

决定走"长上下文一次性抽取"还是现有"逐章抽取"。

判定逻辑（保守优先，避免过度依赖长上下文）：
1. 模型上下文窗口 >= MIN_CONTEXT_FOR_LC（64k tokens），否则不走
2. 估算 prompt token 数 <= ctx * SAFE_INPUT_RATIO，否则不走
3. 章节数 >= MIN_CHAPTERS_FOR_LC（避免单章短文也走长上下文路径）

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4

业界证据：
- NovelHopQA 2025：完整上下文 + 强模型 EM>95%
- LaRA ICML 2025：32k 内长上下文 ≥ RAG，128k 时长上下文 ~ RAG
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from app.services.book_dissect.chapter_splitter import Chapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

# 模型上下文窗口表（tokens）。不在此表的模型走保守 fallback。
# 使用前缀匹配：模型名以表中 key 开头即视为该模型族。
# 仅收录主流且明确支持长上下文的模型（≥64k）；< 64k 模型直接走保守路径。
CONTEXT_WINDOWS: dict[str, int] = {
    # OpenAI
    "gpt-4-turbo": 128_000,
    "gpt-4o": 128_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.5": 200_000,
    "gpt-5": 400_000,
    "o1": 200_000,
    "o3": 200_000,
    "o4": 200_000,
    # Anthropic Claude
    "claude-3-haiku": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-5-haiku": 200_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-7-sonnet": 200_000,
    "claude-haiku-4": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-opus-4": 200_000,
    # Google Gemini
    "gemini-1.5-pro": 2_000_000,
    "gemini-1.5-flash": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.5-pro": 2_000_000,
    # 国内主流
    "deepseek-v3": 64_000,
    "deepseek-r1": 128_000,
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "qwen-max": 32_768,         # 不达门槛但留作对照
    "qwen-2.5-72b": 128_000,
    "qwen-3-72b": 128_000,
    "qwen3": 128_000,           # 通用前缀
    "moonshot-v1-128k": 128_000,
    "moonshot-v1-32k": 32_768,
    "kimi": 128_000,
    "glm-4": 128_000,
    "glm-4.5": 128_000,
    "doubao": 128_000,
    "ernie": 128_000,
}

# 最低门槛：上下文 < 此值不考虑长上下文路径
MIN_CONTEXT_FOR_LC = 64_000

# 安全余量：输入最多占上下文的多少
# 留 45% 给响应（chapter_facts JSON 输出预算）+ prompt 模板（指令、schema 示例）
SAFE_INPUT_RATIO = 0.55

# 章节数最低门槛：少于此值不走长上下文（短文用逐章反而更稳）
MIN_CHAPTERS_FOR_LC = 3

# 中文 1 字符 ≈ 1.0-1.5 tokens（保守按 1.5）
TOKENS_PER_CN_CHAR = 1.5

# 估算时为 prompt 模板（schema 说明、字段释义、指令）预留的 token 数
PROMPT_TEMPLATE_OVERHEAD_TOKENS = 5_000


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class LongContextDecision:
    """路由判定结果。"""

    use_long_context: bool
    reason: str
    estimated_tokens: int
    context_window: int
    safe_input_budget: int
    chapter_count: int
    model: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class LongContextRouter:
    """决定走长上下文一次抽 vs 逐章抽取。"""

    def decide(
        self,
        chapters: list[Chapter],
        model: Optional[str],
    ) -> LongContextDecision:
        """主入口：根据章节总 token 与模型上下文窗口判定。

        Args:
            chapters: 待抽取章节列表
            model: 模型名（可能是 'gpt-4o-2024-08-06' / 'claude-sonnet-4-20250514' 这类带后缀的）

        Returns:
            LongContextDecision
        """
        chapter_count = len(chapters)
        model_str = (model or "").strip()
        ctx = _lookup_context_window(model_str)

        # 估算 token：所有章节正文字符数 × ratio + 模板开销
        total_chars = sum(len(ch.content or "") for ch in chapters)
        estimated_tokens = int(total_chars * TOKENS_PER_CN_CHAR) + PROMPT_TEMPLATE_OVERHEAD_TOKENS
        safe_budget = int(ctx * SAFE_INPUT_RATIO) if ctx else 0

        # 条件 1：章节数门槛
        if chapter_count < MIN_CHAPTERS_FOR_LC:
            return LongContextDecision(
                use_long_context=False,
                reason=f"chapter_count {chapter_count} < {MIN_CHAPTERS_FOR_LC}",
                estimated_tokens=estimated_tokens,
                context_window=ctx,
                safe_input_budget=safe_budget,
                chapter_count=chapter_count,
                model=model_str,
            )

        # 条件 2：模型上下文窗口门槛
        if ctx < MIN_CONTEXT_FOR_LC:
            return LongContextDecision(
                use_long_context=False,
                reason=(
                    f"model {model_str!r} context window {ctx} < {MIN_CONTEXT_FOR_LC}"
                    if ctx else f"unknown model {model_str!r}, fallback to chunked"
                ),
                estimated_tokens=estimated_tokens,
                context_window=ctx,
                safe_input_budget=safe_budget,
                chapter_count=chapter_count,
                model=model_str,
            )

        # 条件 3：估算 token 不能超过预算
        if estimated_tokens > safe_budget:
            return LongContextDecision(
                use_long_context=False,
                reason=(
                    f"estimated {estimated_tokens} tokens > budget {safe_budget} "
                    f"(ctx={ctx}, ratio={SAFE_INPUT_RATIO})"
                ),
                estimated_tokens=estimated_tokens,
                context_window=ctx,
                safe_input_budget=safe_budget,
                chapter_count=chapter_count,
                model=model_str,
            )

        # 全部条件满足
        return LongContextDecision(
            use_long_context=True,
            reason=(
                f"will use long-context one-shot "
                f"(estimated={estimated_tokens}, budget={safe_budget}, ctx={ctx})"
            ),
            estimated_tokens=estimated_tokens,
            context_window=ctx,
            safe_input_budget=safe_budget,
            chapter_count=chapter_count,
            model=model_str,
        )


# ---------------------------------------------------------------------------
# 工具：模型 → 上下文窗口
# ---------------------------------------------------------------------------


@lru_cache(maxsize=128)
def _lookup_context_window(model: str) -> int:
    """根据模型名查找上下文窗口。

    匹配策略：
    1. 精确匹配
    2. 前缀匹配（按 key 长度倒序，避免 'gpt-4' 错配 'gpt-4o'）
    3. 都不命中返回 0

    使用 lru_cache 是因为同一任务内会查多次。
    """
    if not model:
        return 0
    name = model.strip().lower()
    if not name:
        return 0
    # 精确匹配
    for key, ctx in CONTEXT_WINDOWS.items():
        if key.lower() == name:
            return ctx
    # 前缀匹配（按 key 长度倒序，最长优先）
    sorted_keys = sorted(CONTEXT_WINDOWS.keys(), key=lambda k: -len(k))
    for key in sorted_keys:
        if name.startswith(key.lower()):
            return CONTEXT_WINDOWS[key]
    return 0


def register_context_window(model_prefix: str, window: int) -> None:
    """运行时注册新的模型 → 上下文窗口映射（便于配置覆盖）。"""
    if not model_prefix or window <= 0:
        return
    CONTEXT_WINDOWS[model_prefix] = window
    _lookup_context_window.cache_clear()
