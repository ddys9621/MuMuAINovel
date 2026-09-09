"""mcpServers 配置片段归一化

各厂商 README 里 `mcpServers.<name>.type` 写法不统一（http / streamable-http / streamableHttp / sse / remote …），
这里统一映射为 MCPPlugin 的字段字典：
- plugin_type: "http"（Streamable HTTP 与 SSE 都归为 http，传输方式记在 config.transport）或 "stdio"
- config.transport: TRANSPORT_STREAMABLE_HTTP / TRANSPORT_SSE
"""
from typing import Any, Dict
from urllib.parse import urlparse

TRANSPORT_STREAMABLE_HTTP = "streamable_http"
TRANSPORT_SSE = "sse"

_HTTP_TYPE_ALIASES = {"http", "streamable-http", "streamable_http", "streamablehttp", "streamable", "remote"}
_SSE_TYPE_ALIASES = {"sse"}
_STDIO_TYPE_ALIASES = {"stdio", "local"}


class ServerConfigError(ValueError):
    """配置片段无法识别或缺少必要字段"""


def _normalize_type(server_config: Dict[str, Any]) -> str:
    """返回 'http' / 'sse' / 'stdio'"""
    raw = server_config.get("type")
    if raw is None:
        if server_config.get("url"):
            path = urlparse(str(server_config["url"])).path.rstrip("/")
            return "sse" if path.endswith("/sse") else "http"
        if server_config.get("command"):
            return "stdio"
        raise ServerConfigError("配置缺少 type，且无法从 url / command 推断服务器类型")

    lowered = str(raw).strip().lower()
    if lowered in _HTTP_TYPE_ALIASES:
        return "http"
    if lowered in _SSE_TYPE_ALIASES:
        return "sse"
    if lowered in _STDIO_TYPE_ALIASES:
        return "stdio"
    raise ServerConfigError(f"不支持的服务器类型: {raw}（仅支持 http / streamable-http / sse / stdio）")


def parse_server_config(plugin_name: str, server_config: Dict[str, Any]) -> Dict[str, Any]:
    """把标准 mcpServers[plugin_name] 片段转换为 MCPPlugin 字段字典（不含 user_id / category / enabled）"""
    kind = _normalize_type(server_config)

    explicit_transport = str(server_config.get("transport", "")).strip().lower()
    if explicit_transport == TRANSPORT_SSE:
        kind = "sse"
    elif explicit_transport and kind != "stdio":
        kind = "http"

    config: Dict[str, Any] = {}
    if server_config.get("timeout") is not None:
        config["timeout"] = server_config["timeout"]

    data: Dict[str, Any] = {
        "plugin_name": plugin_name,
        "display_name": plugin_name,
        "plugin_type": "stdio" if kind == "stdio" else "http",
        "server_url": None,
        "headers": None,
        "command": None,
        "args": None,
        "env": None,
        "config": config,
    }

    if kind == "stdio":
        if not server_config.get("command"):
            raise ServerConfigError("stdio 类型必须提供 command 字段")
        data["command"] = server_config["command"]
        data["args"] = list(server_config.get("args") or [])
        data["env"] = dict(server_config.get("env") or {})
        return data

    if not server_config.get("url"):
        raise ServerConfigError("http / sse 类型必须提供 url 字段")
    data["server_url"] = str(server_config["url"])
    data["headers"] = dict(server_config.get("headers") or {})
    data["env"] = dict(server_config.get("env") or {}) or None
    config["transport"] = TRANSPORT_SSE if kind == "sse" else TRANSPORT_STREAMABLE_HTTP
    return data
