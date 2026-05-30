"""T2.2: BaseV3Generator._call_and_parse_object 单元测试。

覆盖关键路径：
- 首次成功（dict）→ 直接返回
- LLM 调用异常 → 返回 None
- LLM 返回空 content → 返回 None
- 首次解析失败 + 二次修复成功 → 返回二次修复结果
- 首次解析失败 + 二次修复抛异常 → 返回 None
- 首次解析失败 + 二次修复返回非 dict（如 list）→ 返回 None
- ai_service 未挂载 → 返回 None
- generate_text 返回非 dict（如 str/None）→ 返回 None
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.book_dissect._base_v3_generator import BaseV3Generator


# ============================================================
# 测试用最小化子类
# ============================================================


class _DummyGen(BaseV3Generator):
    """最小化子类，只持有 ai_service。"""

    def __init__(self, ai_service):
        self.ai_service = ai_service


# ============================================================
# helpers
# ============================================================


def make_ai_returning(content):
    ai = MagicMock()
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)
    ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


def make_ai_raising(exc):
    ai = MagicMock()
    ai.generate_text = AsyncMock(side_effect=exc)
    return ai


_BASE_KWARGS = dict(
    prompt="user p",
    system_prompt="sys p",
    temperature=0.4,
    max_tokens=1000,
    label="[Test]",
    schema_hint="a, b, c",
)


# ============================================================
# 成功路径
# ============================================================


@pytest.mark.asyncio
async def test_first_pass_dict_returns_immediately():
    """首次解析得到 dict → 直接返回，不触发二次修复。"""
    ai = make_ai_returning({"a": 1, "b": "ok"})
    gen = _DummyGen(ai)
    result = await gen._call_and_parse_object(**_BASE_KWARGS)
    assert result == {"a": 1, "b": "ok"}
    assert ai.generate_text.await_count == 1


# ============================================================
# 失败路径：LLM 层
# ============================================================


@pytest.mark.asyncio
async def test_llm_exception_returns_none():
    """LLM 调用异常 → 返回 None。"""
    ai = make_ai_raising(RuntimeError("LLM down"))
    gen = _DummyGen(ai)
    result = await gen._call_and_parse_object(**_BASE_KWARGS)
    assert result is None


@pytest.mark.asyncio
async def test_empty_content_returns_none():
    """LLM 返回空 content → 返回 None，不触发二次修复。"""
    ai = make_ai_returning("")
    gen = _DummyGen(ai)
    result = await gen._call_and_parse_object(**_BASE_KWARGS)
    assert result is None
    assert ai.generate_text.await_count == 1


@pytest.mark.asyncio
async def test_non_dict_response_returns_none():
    """generate_text 返回非 dict（如 None / str）→ 返回 None。"""
    ai = MagicMock()
    ai.generate_text = AsyncMock(return_value=None)
    gen = _DummyGen(ai)
    result = await gen._call_and_parse_object(**_BASE_KWARGS)
    assert result is None


@pytest.mark.asyncio
async def test_missing_ai_service_returns_none():
    """ai_service 未挂载 → 返回 None。"""

    class NoAI(BaseV3Generator):
        pass

    gen = NoAI()
    result = await gen._call_and_parse_object(**_BASE_KWARGS)
    assert result is None


# ============================================================
# 二次修复路径（T2.2 的核心新增价值）
# ============================================================


@pytest.mark.asyncio
async def test_first_pass_fail_then_repair_success():
    """首次解析失败 + LLM 二次修复成功 → 返回修复后的 dict。"""
    # 纯文本 + 非 JSON 结构，确保 safe_parse_json 无法解析
    bad_response = "Here is some narrative text without any JSON structure at all."
    ai = make_ai_returning(bad_response)
    gen = _DummyGen(ai)

    repaired_value = {"a": 'with "quote"', "b": 2, "c": "ok"}
    with patch(
        "app.services.book_dissect._base_v3_generator.repair_json_with_llm",
        new=AsyncMock(return_value=repaired_value),
    ) as mock_repair:
        result = await gen._call_and_parse_object(**_BASE_KWARGS)

    assert result == repaired_value
    mock_repair.assert_awaited_once()
    # 验证 schema_hint 传递正确
    call = mock_repair.await_args
    assert call.kwargs["schema_hint"] == "a, b, c"
    assert call.kwargs["expected_type"] == "object"


@pytest.mark.asyncio
async def test_first_pass_fail_then_repair_raises_returns_none():
    """二次修复抛异常 → 优雅返回 None（不让异常向上传播）。"""
    ai = make_ai_returning("not json at all")
    gen = _DummyGen(ai)

    with patch(
        "app.services.book_dissect._base_v3_generator.repair_json_with_llm",
        new=AsyncMock(side_effect=RuntimeError("repair LLM down")),
    ):
        result = await gen._call_and_parse_object(**_BASE_KWARGS)

    assert result is None


@pytest.mark.asyncio
async def test_first_pass_fail_then_repair_returns_non_dict():
    """二次修复返回非 dict（如 list）→ 返回 None。"""
    ai = make_ai_returning("not json")
    gen = _DummyGen(ai)

    with patch(
        "app.services.book_dissect._base_v3_generator.repair_json_with_llm",
        new=AsyncMock(return_value=[1, 2, 3]),
    ):
        result = await gen._call_and_parse_object(**_BASE_KWARGS)

    assert result is None


@pytest.mark.asyncio
async def test_schema_hint_empty_passed_as_none():
    """schema_hint 为空字符串 → 传给 repair_json_with_llm 时应转 None。"""
    ai = make_ai_returning("bad json")
    gen = _DummyGen(ai)

    with patch(
        "app.services.book_dissect._base_v3_generator.repair_json_with_llm",
        new=AsyncMock(return_value={"ok": True}),
    ) as mock_repair:
        kwargs = dict(_BASE_KWARGS)
        kwargs["schema_hint"] = ""
        result = await gen._call_and_parse_object(**kwargs)

    assert result == {"ok": True}
    call = mock_repair.await_args
    # schema_hint="" → 转 None 避免空字符串污染 prompt
    assert call.kwargs["schema_hint"] is None


@pytest.mark.asyncio
async def test_logger_uses_label_prefix(caplog):
    """日志前缀使用 label 参数，便于过滤排查。"""
    import logging

    caplog.set_level(logging.WARNING)
    ai = make_ai_returning("")
    gen = _DummyGen(ai)
    kwargs = dict(_BASE_KWARGS)
    kwargs["label"] = "[拆书V3-测试专用]"
    await gen._call_and_parse_object(**kwargs)
    assert any("[拆书V3-测试专用]" in rec.message for rec in caplog.records)
