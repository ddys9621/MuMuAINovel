"""T2.3.2: ai_service._stream_with_retry helper 单元测试。

覆盖：
- 首次完整流成功 → 不重试
- 0 chunk 时瞬时网络错 → 重试成功
- 0 chunk 时 5xx → 重试成功
- 0 chunk 时持续失败 → 抛出
- 已 yield 1+ chunk 后失败 → 立即抛出，不重试（关键不变量：避免重复 yield）
- 4xx 状态码 → 立即抛出，不重试
- 非可重试异常 → 立即抛出
- 已输出 chunk 在被消费方接收（验证 yield 顺序正确）
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import MagicMock

import httpx
import pytest

from app.services.ai_service import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    _stream_with_retry,
)


# ============================================================
# helpers
# ============================================================


def make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """构造一个指定 status_code 的 HTTPStatusError。"""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.text = f"Error {status_code}"
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=MagicMock(spec=httpx.Request),
        response=mock_resp,
    )


def make_stream_factory(behaviors: list):
    """构造一个 stream factory，按调用顺序返回不同流。

    每个 behavior 可以是：
    - list[str]：完整 yield 这些 chunk 后正常结束
    - tuple(list[str], Exception)：先 yield list 中的 chunk，再 raise 异常
    - Exception：直接 raise（0 chunk）

    返回 (factory, call_count_getter)
    """
    state = {"count": 0}

    def factory() -> AsyncIterator[str]:
        state["count"] += 1
        idx = min(state["count"] - 1, len(behaviors) - 1)
        b = behaviors[idx]

        async def _gen():
            if isinstance(b, BaseException):
                raise b
            if isinstance(b, tuple):
                chunks, exc = b
                for c in chunks:
                    yield c
                raise exc
            if isinstance(b, list):
                for c in b:
                    yield c
                return
            raise TypeError(f"unsupported behavior: {b!r}")

        return _gen()

    return factory, lambda: state["count"]


async def _collect(it: AsyncIterator[str]) -> list[str]:
    out: list[str] = []
    async for x in it:
        out.append(x)
    return out


# ============================================================
# 成功路径
# ============================================================


@pytest.mark.asyncio
async def test_stream_success_first_try_no_retry():
    """首次完整流成功 → 只调一次，全部 chunk 透传。"""
    factory, get_count = make_stream_factory([["a", "b", "c"]])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == ["a", "b", "c"]
    assert get_count() == 1


@pytest.mark.asyncio
async def test_stream_success_empty_stream():
    """流为空也算成功，不重试。"""
    factory, get_count = make_stream_factory([[]])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == []
    assert get_count() == 1


# ============================================================
# 0 chunk 失败 → 可以重试
# ============================================================


@pytest.mark.asyncio
async def test_stream_retry_on_remote_protocol_error_before_first_chunk():
    """握手期 RemoteProtocolError → 重试，第 2 次成功。"""
    factory, get_count = make_stream_factory([
        httpx.RemoteProtocolError("Server disconnected without sending a response"),
        ["a", "b"],
    ])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == ["a", "b"]
    assert get_count() == 2


@pytest.mark.asyncio
async def test_stream_retry_on_connect_timeout_before_first_chunk():
    """ConnectTimeout → 重试。"""
    factory, get_count = make_stream_factory([
        httpx.ConnectTimeout("timeout"),
        ["x"],
    ])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == ["x"]
    assert get_count() == 2


@pytest.mark.asyncio
async def test_stream_retry_on_read_timeout_before_first_chunk():
    """ReadTimeout → 重试。"""
    factory, get_count = make_stream_factory([
        httpx.ReadTimeout("read timeout"),
        ["x"],
    ])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == ["x"]
    assert get_count() == 2


@pytest.mark.asyncio
async def test_stream_retry_on_500_before_first_chunk():
    """5xx → 重试。"""
    factory, get_count = make_stream_factory([
        make_http_status_error(500),
        ["ok"],
    ])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == ["ok"]
    assert get_count() == 2


@pytest.mark.asyncio
async def test_stream_retry_on_429_before_first_chunk():
    """429 限流 → 重试。"""
    factory, get_count = make_stream_factory([
        make_http_status_error(429),
        ["ok"],
    ])
    result = await _collect(
        _stream_with_retry(factory, max_retries=3, base_delay=0.001)
    )
    assert result == ["ok"]
    assert get_count() == 2


@pytest.mark.asyncio
async def test_stream_retry_on_502_503_504():
    """502 / 503 / 504 都重试。"""
    for code in (502, 503, 504):
        factory, get_count = make_stream_factory([
            make_http_status_error(code),
            ["ok"],
        ])
        result = await _collect(
            _stream_with_retry(factory, max_retries=3, base_delay=0.001)
        )
        assert result == ["ok"]
        assert get_count() == 2, f"code={code}"


# ============================================================
# 关键不变量：已 yield 后失败必须立即抛出，绝不重试
# ============================================================


@pytest.mark.asyncio
async def test_stream_already_yielded_then_network_error_raises_immediately():
    """已 yield 过 chunk 再断 → 立即抛，不重试（避免重复内容）。"""
    factory, get_count = make_stream_factory([
        (["partial1", "partial2"], httpx.RemoteProtocolError("mid-stream disconnect")),
        ["should_not_retry"],
    ])
    chunks: list[str] = []
    with pytest.raises(httpx.RemoteProtocolError):
        async for chunk in _stream_with_retry(
            factory, max_retries=3, base_delay=0.001
        ):
            chunks.append(chunk)
    # 部分 chunk 已被消费方接收
    assert chunks == ["partial1", "partial2"]
    # 关键：只调用了 1 次工厂，没有 retry
    assert get_count() == 1


@pytest.mark.asyncio
async def test_stream_already_yielded_then_5xx_raises_immediately():
    """已 yield 过 chunk 再收到 5xx → 立即抛，不重试。"""
    factory, get_count = make_stream_factory([
        (["p1"], make_http_status_error(500)),
        ["nope"],
    ])
    chunks: list[str] = []
    with pytest.raises(httpx.HTTPStatusError):
        async for chunk in _stream_with_retry(
            factory, max_retries=3, base_delay=0.001
        ):
            chunks.append(chunk)
    assert chunks == ["p1"]
    assert get_count() == 1


# ============================================================
# 不可重试异常
# ============================================================


@pytest.mark.asyncio
async def test_stream_no_retry_on_4xx():
    """4xx → 立即抛，不重试（不浪费 quota）。"""
    for code in (400, 401, 403, 404, 422):
        factory, get_count = make_stream_factory([
            make_http_status_error(code),
            ["nope"],
        ])
        with pytest.raises(httpx.HTTPStatusError):
            await _collect(
                _stream_with_retry(factory, max_retries=3, base_delay=0.001)
            )
        assert get_count() == 1, f"code={code} should not retry"


@pytest.mark.asyncio
async def test_stream_no_retry_on_value_error():
    """非可重试异常 → 立即抛。"""
    factory, get_count = make_stream_factory([
        ValueError("bad config"),
        ["nope"],
    ])
    with pytest.raises(ValueError):
        await _collect(
            _stream_with_retry(factory, max_retries=3, base_delay=0.001)
        )
    assert get_count() == 1


# ============================================================
# 持续失败
# ============================================================


@pytest.mark.asyncio
async def test_stream_retries_exhausted_raises_last_exception():
    """持续 0 chunk 网络错 → 重试 N 次后抛出最后一次的异常。"""
    factory, get_count = make_stream_factory([
        httpx.RemoteProtocolError("first"),
        httpx.RemoteProtocolError("second"),
        httpx.RemoteProtocolError("third"),
        ["should_not_reach"],
    ])
    with pytest.raises(httpx.RemoteProtocolError):
        await _collect(
            _stream_with_retry(factory, max_retries=3, base_delay=0.001)
        )
    assert get_count() == 3


@pytest.mark.asyncio
async def test_stream_persistent_5xx_raises_after_retries():
    """持续 5xx → 重试 N 次后抛出。"""
    factory, get_count = make_stream_factory([
        make_http_status_error(503),
        make_http_status_error(503),
        make_http_status_error(503),
        ["nope"],
    ])
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await _collect(
            _stream_with_retry(factory, max_retries=3, base_delay=0.001)
        )
    assert exc_info.value.response.status_code == 503
    assert get_count() == 3


# ============================================================
# 配置参数
# ============================================================


@pytest.mark.asyncio
async def test_stream_max_retries_custom():
    """自定义 max_retries=1（仅首次，无重试）。"""
    factory, get_count = make_stream_factory([
        httpx.RemoteProtocolError("once"),
        ["should_not_reach"],
    ])
    with pytest.raises(httpx.RemoteProtocolError):
        await _collect(
            _stream_with_retry(factory, max_retries=1, base_delay=0.001)
        )
    assert get_count() == 1


@pytest.mark.asyncio
async def test_stream_defaults_match_call_with_retry():
    """流式 retry 默认值与非流式一致（max_retries=3, base_delay=1.0）。"""
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_BASE_DELAY == 1.0


# ============================================================
# 混合场景：握手失败 → 重试成功 → 中途断 → 抛
# ============================================================


@pytest.mark.asyncio
async def test_stream_first_retry_then_mid_stream_error_raises():
    """第 1 次握手失败重试 → 第 2 次部分 yield 后断 → 立即抛。"""
    factory, get_count = make_stream_factory([
        httpx.ConnectError("handshake fail"),
        (["a", "b"], httpx.RemoteProtocolError("mid-stream")),
    ])
    chunks: list[str] = []
    with pytest.raises(httpx.RemoteProtocolError):
        async for chunk in _stream_with_retry(
            factory, max_retries=3, base_delay=0.001
        ):
            chunks.append(chunk)
    assert chunks == ["a", "b"]
    # 第 1 次握手挂 → retry；第 2 次产出 2 chunk 后断 → 不再 retry
    assert get_count() == 2
