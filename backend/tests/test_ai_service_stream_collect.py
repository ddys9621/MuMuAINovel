"""ai_service.generate_text_stream_collect 单元测试。

覆盖：
- 正常流：所有 chunk 累积到 content，返回 stream_complete
- 空流：返回空 content
- 单 chunk 流
- 流式底层抛异常：原样传播给调用方
- None / 空 chunk 不入累积，但 chunk_count 也不计入
- 默认 context 取 model 名做日志标签（不抛错）
- 自定义 context 不影响返回值
"""
from __future__ import annotations

from typing import AsyncIterator, List
from unittest.mock import patch

import pytest

from app.services.ai_service import AIService


# ============================================================
# helpers
# ============================================================


def _make_stream(chunks: List[str]):
    """构造一个能多次"重新调用"的 async 流 factory，每次产同样的 chunks。"""

    async def _gen(**_kwargs) -> AsyncIterator[str]:
        for c in chunks:
            yield c

    return _gen


def _make_failing_stream(exc: Exception):
    """构造一个流：0 chunk 直接抛异常。"""

    async def _gen(**_kwargs) -> AsyncIterator[str]:
        if False:  # pragma: no cover - 保证是 async generator
            yield ""
        raise exc

    return _gen


def _make_partial_then_fail(chunks: List[str], exc: Exception):
    """构造一个流：先 yield 几个 chunk，再抛异常。"""

    async def _gen(**_kwargs) -> AsyncIterator[str]:
        for c in chunks:
            yield c
        raise exc

    return _gen


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def service() -> AIService:
    """构造一个最小可用的 AIService（不实际连任何 API）。"""
    svc = AIService.__new__(AIService)
    svc.api_provider = "openai"
    svc.default_model = "test-model"
    svc.default_temperature = 0.7
    svc.default_max_tokens = 4000
    svc.openai_client = None
    svc.openai_http_client = None
    svc.openai_api_key = None
    svc.openai_base_url = None
    svc.anthropic_client = None
    svc.anthropic_http_client = None
    svc._closed = False
    return svc


# ============================================================
# Tests
# ============================================================


@pytest.mark.asyncio
async def test_collect_normal_stream_concatenates_all_chunks(service):
    """正常多 chunk 流应被无损拼接，finish_reason=stream_complete。"""
    chunks = ["hello ", "world", "!"]
    with patch.object(service, "generate_text_stream", _make_stream(chunks)):
        result = await service.generate_text_stream_collect(prompt="x")

    assert result["content"] == "hello world!"
    assert result["finish_reason"] == "stream_complete"


@pytest.mark.asyncio
async def test_collect_empty_stream_returns_empty_content(service):
    """0 chunk 流应返回空 content，仍是 stream_complete。"""
    with patch.object(service, "generate_text_stream", _make_stream([])):
        result = await service.generate_text_stream_collect(prompt="x")

    assert result["content"] == ""
    assert result["finish_reason"] == "stream_complete"


@pytest.mark.asyncio
async def test_collect_single_chunk_stream(service):
    """单 chunk 流应正常返回该 chunk。"""
    with patch.object(service, "generate_text_stream", _make_stream(["only"])):
        result = await service.generate_text_stream_collect(prompt="x")

    assert result["content"] == "only"


@pytest.mark.asyncio
async def test_collect_propagates_underlying_exception(service):
    """底层流抛异常 → 调用方应能捕获到（不被静默吞掉）。"""
    exc = RuntimeError("upstream boom")
    with patch.object(service, "generate_text_stream", _make_failing_stream(exc)):
        with pytest.raises(RuntimeError, match="upstream boom"):
            await service.generate_text_stream_collect(prompt="x")


@pytest.mark.asyncio
async def test_collect_propagates_mid_stream_exception(service):
    """已 yield 部分 chunk 后抛异常 → 调用方应能捕获，content 由上层处理。"""
    exc = RuntimeError("mid stream boom")
    with patch.object(
        service,
        "generate_text_stream",
        _make_partial_then_fail(["partial "], exc),
    ):
        with pytest.raises(RuntimeError, match="mid stream boom"):
            await service.generate_text_stream_collect(prompt="x")


@pytest.mark.asyncio
async def test_collect_skips_none_and_empty_chunks(service):
    """None / "" chunk 不应进入 content；非空 chunk 全部进入。"""

    async def _gen_mixed(**_kwargs) -> AsyncIterator[str]:
        yield "a"
        yield ""  # 空 chunk
        yield None  # type: ignore[misc]
        yield "b"

    with patch.object(service, "generate_text_stream", _gen_mixed):
        result = await service.generate_text_stream_collect(prompt="x")

    assert result["content"] == "ab"


@pytest.mark.asyncio
async def test_collect_custom_context_does_not_affect_result(service):
    """自定义 context 仅用于日志，不影响返回 content / finish_reason。"""
    with patch.object(service, "generate_text_stream", _make_stream(["a", "b"])):
        result = await service.generate_text_stream_collect(
            prompt="x", context="BridgePlanning-test"
        )

    assert result["content"] == "ab"
    assert result["finish_reason"] == "stream_complete"


@pytest.mark.asyncio
async def test_collect_default_context_uses_model_name(service):
    """未传 context 时应用 model 名做日志 label，不抛错（仅验证不崩）。"""
    with patch.object(service, "generate_text_stream", _make_stream(["a"])):
        result = await service.generate_text_stream_collect(
            prompt="x", model="claude-opus-4"
        )

    assert result["content"] == "a"


@pytest.mark.asyncio
async def test_collect_forwards_all_kwargs_to_stream(service):
    """temperature / max_tokens / provider / system_prompt 应原样传给底层 stream。"""
    captured = {}

    async def _gen_capture(**kwargs) -> AsyncIterator[str]:
        captured.update(kwargs)
        yield "ok"

    with patch.object(service, "generate_text_stream", _gen_capture):
        await service.generate_text_stream_collect(
            prompt="hello",
            provider="anthropic",
            model="claude-sonnet-4-5",
            temperature=0.3,
            max_tokens=8000,
            system_prompt="you are a writer",
        )

    assert captured["prompt"] == "hello"
    assert captured["provider"] == "anthropic"
    assert captured["model"] == "claude-sonnet-4-5"
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 8000
    assert captured["system_prompt"] == "you are a writer"
