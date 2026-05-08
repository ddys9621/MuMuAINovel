"""拆书 V3.1 LongContextRouter 验收测试。

覆盖：
- 上下文窗口表查找：精确 / 前缀匹配 / 未知模型
- 路由判定：章节数 / 上下文窗口 / 估算 token 三类阈值
- 边界场景：超长单本 / 短篇 / 未知模型 / 极小模型
- 运行时注册新模型

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4
"""

import pytest

from app.services.book_dissect.chapter_splitter import Chapter
from app.services.book_dissect.long_context_router import (
    CONTEXT_WINDOWS,
    LongContextDecision,
    LongContextRouter,
    MIN_CHAPTERS_FOR_LC,
    MIN_CONTEXT_FOR_LC,
    SAFE_INPUT_RATIO,
    TOKENS_PER_CN_CHAR,
    _lookup_context_window,
    register_context_window,
)


# ============================================================
# fixtures
# ============================================================


def make_chapters(count: int, chars_per_chapter: int = 1000) -> list[Chapter]:
    return [
        Chapter(
            chapter_number=i + 1,
            title=f"第{i+1}章",
            raw_title=f"第{i+1}章",
            content="测试内容" * (chars_per_chapter // 4),
            word_count=chars_per_chapter,
            kind="chapter",
        )
        for i in range(count)
    ]


# ============================================================
# _lookup_context_window：模型查找
# ============================================================


class TestLookupContextWindow:
    def setup_method(self):
        # 每次清缓存，避免不同测试串扰
        _lookup_context_window.cache_clear()

    def test_exact_match(self):
        assert _lookup_context_window("gpt-4o") == 128_000

    def test_prefix_match_with_date_suffix(self):
        """带日期后缀的模型名应通过前缀匹配命中。"""
        assert _lookup_context_window("gpt-4o-2024-08-06") == 128_000
        assert _lookup_context_window("claude-sonnet-4-20250514") == 200_000

    def test_prefix_longest_first(self):
        """同时匹配多个前缀时取最长匹配。"""
        # 'gpt-4o' 比 'gpt-4' 更长，应优先匹配
        # 注意：CONTEXT_WINDOWS 中没有 'gpt-4'（只有 'gpt-4-turbo' 'gpt-4o' 'gpt-4.1' 'gpt-4.5'）
        # 但仍验证最长优先逻辑
        assert _lookup_context_window("gpt-4o-mini-realtime") == 128_000

    def test_case_insensitive(self):
        assert _lookup_context_window("GPT-4O") == 128_000
        assert _lookup_context_window("Claude-3-5-Sonnet-Latest") == 200_000

    def test_unknown_model_returns_zero(self):
        assert _lookup_context_window("unknown-model-xyz") == 0
        assert _lookup_context_window("") == 0
        assert _lookup_context_window(None) == 0  # type: ignore

    def test_small_context_model(self):
        """qwen-max 32k 仍可查到，但调用方应据此判定不走长上下文。"""
        assert _lookup_context_window("qwen-max") == 32_768

    def test_register_runtime(self):
        """运行时注册新模型应即时生效。"""
        register_context_window("custom-model-xl", 500_000)
        try:
            assert _lookup_context_window("custom-model-xl") == 500_000
            # 带后缀也能命中
            assert _lookup_context_window("custom-model-xl-v2") == 500_000
        finally:
            CONTEXT_WINDOWS.pop("custom-model-xl", None)
            _lookup_context_window.cache_clear()


# ============================================================
# LongContextRouter：路由判定
# ============================================================


class TestRouterDecide:
    def setup_method(self):
        _lookup_context_window.cache_clear()

    def test_short_novel_with_long_context_model_uses_lc(self):
        """中短篇 + claude-sonnet-4 应走长上下文。

        50 章 × 1000 字 = 50k 字 → ~75k tokens + 5k overhead = 80k tokens
        budget = 200k × 0.55 = 110k → 通过
        """
        chapters = make_chapters(50, chars_per_chapter=1000)
        router = LongContextRouter()
        decision = router.decide(chapters, model="claude-sonnet-4")
        assert decision.use_long_context is True
        assert decision.context_window == 200_000
        assert decision.estimated_tokens > 0
        assert decision.estimated_tokens <= decision.safe_input_budget

    def test_long_novel_does_not_use_lc(self):
        """超长小说估算 token 超出预算，应走逐章。"""
        chapters = make_chapters(500, chars_per_chapter=3000)  # 500 章 × 3k 字 = 1.5M 字 → 2.25M tokens
        router = LongContextRouter()
        decision = router.decide(chapters, model="claude-sonnet-4")  # 200k ctx
        assert decision.use_long_context is False
        assert "tokens" in decision.reason or "budget" in decision.reason

    def test_huge_novel_with_gemini_2m_uses_lc(self):
        """超大上下文（gemini 2.5 pro = 2M）能放下大长篇。"""
        chapters = make_chapters(300, chars_per_chapter=2000)  # 300 × 2k = 600k 字 = 900k tokens
        router = LongContextRouter()
        decision = router.decide(chapters, model="gemini-2.5-pro")
        assert decision.use_long_context is True
        assert decision.context_window == 2_000_000

    def test_small_context_model_blocked(self):
        """上下文 < MIN_CONTEXT_FOR_LC 即使内容很短也不走长上下文。"""
        chapters = make_chapters(10, chars_per_chapter=500)  # 微型小说
        router = LongContextRouter()
        decision = router.decide(chapters, model="qwen-max")  # 32k ctx
        assert decision.use_long_context is False
        assert "context window" in decision.reason

    def test_unknown_model_falls_back_to_chunked(self):
        """未知模型保守走逐章。"""
        chapters = make_chapters(10, chars_per_chapter=500)
        router = LongContextRouter()
        decision = router.decide(chapters, model="unknown-future-model")
        assert decision.use_long_context is False
        assert "unknown" in decision.reason.lower()
        assert decision.context_window == 0

    def test_too_few_chapters_skips_lc(self):
        """章节数 < MIN_CHAPTERS_FOR_LC 不走长上下文。"""
        chapters = make_chapters(MIN_CHAPTERS_FOR_LC - 1, chars_per_chapter=100)
        router = LongContextRouter()
        decision = router.decide(chapters, model="claude-sonnet-4")
        assert decision.use_long_context is False
        assert "chapter_count" in decision.reason

    def test_empty_chapters(self):
        """空章节列表直接 False。"""
        router = LongContextRouter()
        decision = router.decide([], model="claude-sonnet-4")
        assert decision.use_long_context is False
        assert decision.chapter_count == 0

    def test_none_model_falls_back(self):
        """model=None 应保守走逐章，不抛异常。"""
        chapters = make_chapters(10, chars_per_chapter=500)
        router = LongContextRouter()
        decision = router.decide(chapters, model=None)
        assert decision.use_long_context is False
        assert decision.context_window == 0

    def test_decision_includes_metadata(self):
        """decision 应包含足够元数据用于日志。"""
        chapters = make_chapters(20, chars_per_chapter=1500)
        router = LongContextRouter()
        decision = router.decide(chapters, model="gpt-4o")
        assert isinstance(decision, LongContextDecision)
        assert decision.model == "gpt-4o"
        assert decision.chapter_count == 20
        assert decision.context_window == 128_000
        # 估算应大致 = 20*1500*1.5 + overhead = 45000 + 5000 = ~50000
        assert 40_000 < decision.estimated_tokens < 60_000

    def test_safe_input_ratio_respected(self):
        """估算 token 不能超过 ctx * SAFE_INPUT_RATIO。"""
        # 构造紧贴边界的内容：让 estimated_tokens ≈ 0.5 * ctx → 应通过
        # 200k ctx × 0.55 = 110k input budget
        # 让 chapters 总字符数约 70k 字（→ 105k tokens + 5k overhead = 110k）
        chapters = make_chapters(70, chars_per_chapter=1000)  # 70k 字
        router = LongContextRouter()
        decision = router.decide(chapters, model="claude-sonnet-4")
        # 估算约 110k，预算约 110k → 边界，可能 True 也可能 False
        # 真正测试：构造明显超过边界的情况
        chapters_over = make_chapters(150, chars_per_chapter=1000)  # 150k 字 → 230k tokens
        decision_over = router.decide(chapters_over, model="claude-sonnet-4")
        assert decision_over.use_long_context is False


class TestRouterConsistency:
    def test_same_input_same_decision(self):
        """同样输入应得到一致结果（lru_cache 不应误命中）。"""
        chapters = make_chapters(10, chars_per_chapter=1000)
        router = LongContextRouter()
        d1 = router.decide(chapters, model="claude-sonnet-4")
        d2 = router.decide(chapters, model="claude-sonnet-4")
        assert d1.use_long_context == d2.use_long_context
        assert d1.estimated_tokens == d2.estimated_tokens

    def test_different_models_different_decisions(self):
        """同一章节列表，不同模型可能产生不同决策。"""
        chapters = make_chapters(20, chars_per_chapter=2000)  # 40k 字 = 60k tokens
        router = LongContextRouter()
        # claude-sonnet-4 200k ctx → 应通过
        d_claude = router.decide(chapters, model="claude-sonnet-4")
        # qwen-max 32k ctx → 不通过
        d_qwen = router.decide(chapters, model="qwen-max")
        assert d_claude.use_long_context is True
        assert d_qwen.use_long_context is False
