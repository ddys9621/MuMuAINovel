"""R6/R8 拆书参考包注入回归测试 —— 剧情线 + 剧情线节点 (beats)。

只覆盖最关键不变量：
- 阶段 2 _generate_beats_for_lines_with_ai 在 dissect_ref_block 非空时把它拼到 prompt 末尾
- 空串时不影响 prompt
- ai_service 调用被传入「拼好后的最终 prompt」

不覆盖 generate_plot_lines 端到端流程（涉及 ORM/DB fixture 量太大），
只验证最易踩坑的注入拼接行为。
"""
from __future__ import annotations

import pytest

from app.services.plot_generation_service import PlotGenerationService


class _StubAIService:
    """记录最近一次 generate_text 调用的 prompt。"""

    def __init__(self):
        self.last_prompt: str | None = None
        # 返回值给 _validate_and_normalize_beats 用 —— 至少 3 个 beat，权重 1.0
        self.response = (
            '```json\n'
            '['
            '{"beat_index": 1, "title": "起", "description": "...", "weight": 0.4},'
            '{"beat_index": 2, "title": "承", "description": "...", "weight": 0.3},'
            '{"beat_index": 3, "title": "转", "description": "...", "weight": 0.2},'
            '{"beat_index": 4, "title": "合", "description": "...", "weight": 0.1}'
            ']\n```'
        )

    async def generate_text(self, prompt: str, **_):
        self.last_prompt = prompt
        return self.response


@pytest.mark.asyncio
async def test_beats_prompt_appends_dissect_ref_block_when_provided():
    """dissect_ref_block 非空 → 拼到 prompt 末尾。"""
    ai = _StubAIService()
    svc = PlotGenerationService(ai)
    project_data = {"title": "T", "genre": "G", "theme": "X"}
    lines = [{"index": 1, "title": "线1", "description": "desc"}]

    ref_block = "[参考结构骨架]\n《范本》：起承转合"
    await svc._generate_beats_for_lines_with_ai(
        project_data=project_data,
        lines=lines,
        dissect_ref_block=ref_block,
    )

    assert ai.last_prompt is not None
    assert ai.last_prompt.endswith(ref_block), \
        "dissect_ref_block 应拼到 prompt 末尾，便于 LLM 视为最新强引导"


@pytest.mark.asyncio
async def test_beats_prompt_unchanged_when_dissect_ref_block_empty():
    """空串 → prompt 不变（不应误拼空白尾段）。"""
    ai = _StubAIService()
    svc = PlotGenerationService(ai)
    project_data = {"title": "T", "genre": "G", "theme": "X"}
    lines = [{"index": 1, "title": "线1", "description": "desc"}]

    await svc._generate_beats_for_lines_with_ai(
        project_data=project_data,
        lines=lines,
        dissect_ref_block="",
    )

    assert ai.last_prompt is not None
    # 末尾不能莫名其妙带 \n\n（空 ref_block 不应触发拼接）
    assert not ai.last_prompt.endswith("\n\n"), \
        "空 dissect_ref_block 不应在 prompt 末尾追加多余空行"


@pytest.mark.asyncio
async def test_beats_prompt_default_dissect_ref_block_is_empty():
    """不传 dissect_ref_block 时使用默认空串，等价于「不注入」。"""
    ai = _StubAIService()
    svc = PlotGenerationService(ai)
    project_data = {"title": "T", "genre": "G", "theme": "X"}
    lines = [{"index": 1, "title": "线1", "description": "desc"}]

    await svc._generate_beats_for_lines_with_ai(
        project_data=project_data,
        lines=lines,
        # 故意不传 dissect_ref_block —— 验证默认 ""
    )

    # 不应包含 R6 注入头（参考某书等关键词都不应出现）
    assert ai.last_prompt is not None
    assert "[参考结构骨架]" not in ai.last_prompt
