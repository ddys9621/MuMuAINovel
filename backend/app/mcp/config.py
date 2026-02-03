"""MCP模块配置常量"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MCPConfig:
    """MCP模块配置常量（不可变）"""
    
    # 连接池配置
    MAX_CLIENTS: int = 1000  # 最大客户端数量
    CLIENT_TTL_SECONDS: int = 3600  # 客户端过期时间（1小时）
    IDLE_TIMEOUT_SECONDS: int = 1800  # 空闲超时（30分钟）
    
    # 健康检查配置
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60  # 健康检查间隔
    ERROR_RATE_CRITICAL: float = 0.7  # 严重错误率阈值
    ERROR_RATE_WARNING: float = 0.4  # 警告错误率阈值
    MIN_REQUESTS_FOR_HEALTH_CHECK: int = 10  # 进行健康检查的最小请求数
    
    # 清理任务配置
    CLEANUP_INTERVAL_SECONDS: int = 300  # 清理任务间隔（5分钟）
    
    # 缓存配置
    TOOL_CACHE_TTL_MINUTES: int = 10  # 工具定义缓存TTL
    
    # 重试配置
    MAX_RETRIES: int = 3  # 最大重试次数
    BASE_RETRY_DELAY_SECONDS: float = 1.0  # 基础重试延迟
    MAX_RETRY_DELAY_SECONDS: float = 10.0  # 最大重试延迟
    
    # 超时配置
    DEFAULT_TIMEOUT_SECONDS: float = 60.0  # 默认超时时间
    TOOL_CALL_TIMEOUT_SECONDS: float = 60.0  # 工具调用超时时间
    
    # 日志配置
    LOG_TOOL_ARGUMENTS: bool = True  # 是否记录工具参数
    LOG_TOOL_RESULTS: bool = False  # 是否记录工具结果（可能很大）


# 全局配置实例
mcp_config = MCPConfig()