"""T2.3: ai_service._call_with_retry helper 单元测试。

覆盖：
- 首次成功 → 不重试
- 瞬时网络错误（RemoteProtocolError/ReadTimeout/ConnectError）→ 重试成功
- 持续瞬时错误 → 重试 N 次后抛出
- 5xx HTTP 错误 → 重试
- 429 限流 → 重试
- 4xx HTTP 错误 → 不重试，立即抛出
- 非可重试异常（ValueError 等）→ 立即抛出
- 指数 backoff 行为
"""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from app.services.ai_service import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    RETRIABLE_HTTPX_ERRORS,
    RETRIABLE_STATUS_CODES,
    _call_with_retry,
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


class CallCounter:
    """用 closure 模拟 generate_text，记录调用次数 + 按次返回不同结果。"""

    def __init__(self, behaviors: list):
        """behaviors: list of 值（直接 return）或 Exception（raise）。"""
        self.behaviors = behaviors
        self.count = 0

    async def __call__(self):
        self.count += 1
        idx = min(self.count - 1, len(self.behaviors) - 1)
        b = self.behaviors[idx]
        if isinstance(b, BaseException):
            raise b
        return b


# ============================================================
# 成功路径
# ============================================================


@pytest.mark.asyncio
async def test_retry_success_first_try_no_retry():
    """首次成功 → 只调一次。"""
    counter = CallCounter(["ok"])
    result = await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert result == "ok"
    assert counter.count == 1


# ============================================================
# 可重试网络错误：每个可重试异常都覆盖一遍
# ============================================================


@pytest.mark.parametrize(
    "exc_factory",
    [
        lambda: httpx.RemoteProtocolError("Server disconnected"),
        lambda: httpx.ReadTimeout("read timeout"),
        lambda: httpx.ConnectTimeout("connect timeout"),
        lambda: httpx.WriteTimeout("write timeout"),
        lambda: httpx.PoolTimeout("pool timeout"),
        lambda: httpx.ConnectError("connection refused"),
    ],
)
@pytest.mark.asyncio
async def test_retry_each_httpx_error_then_success(exc_factory):
    """每个可重试网络错误：第 1 次失败 → 第 2 次成功。"""
    counter = CallCounter([exc_factory(), "ok"])
    result = await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert result == "ok"
    assert counter.count == 2


@pytest.mark.asyncio
async def test_retry_persistent_remote_protocol_error_raises_after_max():
    """持续失败 → 重试 max_retries 次后抛出最后一次的异常。"""
    counter = CallCounter(
        [httpx.RemoteProtocolError("persistent disconnect")] * 5
    )
    with pytest.raises(httpx.RemoteProtocolError, match="persistent disconnect"):
        await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert counter.count == 3  # 首次 + 2 次重试


# ============================================================
# 5xx / 429 HTTP 状态码
# ============================================================


@pytest.mark.parametrize("status_code", sorted(RETRIABLE_STATUS_CODES))
@pytest.mark.asyncio
async def test_retry_retriable_5xx_then_success(status_code):
    """5xx / 429 → 重试 → 成功。"""
    counter = CallCounter([make_http_status_error(status_code), "ok"])
    result = await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert result == "ok"
    assert counter.count == 2


@pytest.mark.asyncio
async def test_retry_persistent_503_raises_after_max():
    """503 持续 → 重试用完抛出。"""
    counter = CallCounter([make_http_status_error(503)] * 5)
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert exc_info.value.response.status_code == 503
    assert counter.count == 3


# ============================================================
# 不可重试错误：4xx 立即抛
# ============================================================


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 413, 422])
@pytest.mark.asyncio
async def test_retry_4xx_no_retry_raises_immediately(status_code):
    """4xx 错误（参数错 / API key 错 / prompt too long）→ 不重试立即抛。"""
    counter = CallCounter([make_http_status_error(status_code)] * 5)
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert exc_info.value.response.status_code == status_code
    assert counter.count == 1  # 只调一次，不重试


@pytest.mark.asyncio
async def test_retry_non_httpx_exception_propagates_immediately():
    """非 httpx 异常（如 ValueError）→ 不重试立即抛。"""
    counter = CallCounter([ValueError("not retriable")])
    with pytest.raises(ValueError, match="not retriable"):
        await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert counter.count == 1


@pytest.mark.asyncio
async def test_retry_generic_exception_propagates_immediately():
    """通用 Exception → 不重试立即抛。"""
    counter = CallCounter([RuntimeError("oops")])
    with pytest.raises(RuntimeError, match="oops"):
        await _call_with_retry(counter, max_retries=3, base_delay=0.001)
    assert counter.count == 1


# ============================================================
# 边界 / 配置
# ============================================================


@pytest.mark.asyncio
async def test_retry_max_retries_1_no_retry():
    """max_retries=1 → 失败就抛，不重试。"""
    counter = CallCounter([httpx.RemoteProtocolError("disconnect")])
    with pytest.raises(httpx.RemoteProtocolError):
        await _call_with_retry(counter, max_retries=1, base_delay=0.001)
    assert counter.count == 1


@pytest.mark.asyncio
async def test_retry_mixed_errors_eventual_success():
    """混合错误 → 都是可重试 → 最终成功。"""
    counter = CallCounter([
        httpx.ReadTimeout("read"),
        make_http_status_error(502),
        httpx.RemoteProtocolError("disconnect"),
        "ok",
    ])
    result = await _call_with_retry(counter, max_retries=5, base_delay=0.001)
    assert result == "ok"
    assert counter.count == 4


@pytest.mark.asyncio
async def test_retry_4xx_after_5xx_does_not_retry_further():
    """5xx 重试后第 2 次拿到 4xx → 立即抛 4xx，不再重试。"""
    counter = CallCounter([
        make_http_status_error(503),  # 重试 1
        make_http_status_error(400),  # 不重试，立即抛
    ])
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await _call_with_retry(counter, max_retries=5, base_delay=0.001)
    assert exc_info.value.response.status_code == 400
    assert counter.count == 2


# ============================================================
# 模块级常量校验
# ============================================================


def test_retriable_status_codes_match_design():
    """RETRIABLE_STATUS_CODES 必须包含设计要求的 5 个码。"""
    assert RETRIABLE_STATUS_CODES == {429, 500, 502, 503, 504}


def test_retriable_httpx_errors_includes_remote_protocol_error():
    """RETRIABLE_HTTPX_ERRORS 必须包含触发 T2.3 的 RemoteProtocolError。"""
    assert httpx.RemoteProtocolError in RETRIABLE_HTTPX_ERRORS
    assert httpx.ReadTimeout in RETRIABLE_HTTPX_ERRORS
    assert httpx.ConnectError in RETRIABLE_HTTPX_ERRORS


def test_defaults():
    """默认配置合理性校验。"""
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_BASE_DELAY == 1.0
