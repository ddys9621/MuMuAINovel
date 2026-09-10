"""统一日志配置模块 - Uvicorn风格"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class UvicornFormatter(logging.Formatter):
    """Uvicorn风格的日志格式化器"""
    
    # 日志级别颜色（ANSI转义码）
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def __init__(self, use_colors: bool = True):
        """
        初始化格式化器
        
        Args:
            use_colors: 是否使用颜色（控制台输出使用，文件输出不使用）
        """
        super().__init__()
        self.use_colors = use_colors
    
    def format(self, record):
        """格式化日志记录为 Uvicorn 风格"""
        # 获取日志级别名称
        levelname = record.levelname
        
        # 添加颜色（如果启用且终端支持）
        if self.use_colors and sys.stderr.isatty():
            colored_level = f"{self.COLORS.get(levelname, '')}{levelname}{self.RESET}"
        else:
            colored_level = levelname
        
        # 添加请求追踪ID（如果存在）
        request_id = getattr(record, 'request_id', None)
        request_id_str = f" [{request_id}]" if request_id else ""
        
        # Uvicorn风格格式: INFO:     module_name - message [request_id]
        # 注意：INFO后面有5个空格，保持对齐
        return f"{colored_level}:     {record.name}{request_id_str} - {record.getMessage()}"


# 全局标志，防止重复初始化
_logging_configured = False

def setup_logging(
    level: str = "INFO",
    log_to_file: bool = False,
    log_file_path: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 30
):
    """
    配置统一的 Uvicorn 风格日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否输出到文件
        log_file_path: 日志文件路径
        max_bytes: 单个日志文件最大字节数（默认10MB）
        backup_count: 保留的备份文件数量（默认30个）
    """
    global _logging_configured
    
    # 如果已经配置过，直接返回
    if _logging_configured:
        return logging.getLogger()
    
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除已有的处理器，避免重复
    root_logger.handlers.clear()
    
    # 1. 创建控制台处理器（带颜色）
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = UvicornFormatter(use_colors=True)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 2. 创建文件处理器（如果启用）
    if log_to_file and log_file_path:
        # 确保日志目录存在
        log_file = Path(log_file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用RotatingFileHandler实现日志轮转
        file_handler = RotatingFileHandler(
            filename=log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        # 文件日志不使用颜色
        file_formatter = UvicornFormatter(use_colors=False)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # 记录日志配置信息
        root_logger.info(f"日志文件输出已启用: {log_file_path}")
        root_logger.info(f"日志轮转配置: 单文件最大{max_bytes / 1024 / 1024:.1f}MB, 保留{backup_count}个备份")
    
    # 配置第三方库的日志级别
    _configure_third_party_loggers()
    
    # 标记为已配置
    _logging_configured = True
    
    return root_logger


def _configure_third_party_loggers():
    """配置第三方库的日志级别"""
    # SQLAlchemy - 禁用SQL日志
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
    
    # Watchfiles - 开发时的文件监控，降低级别
    logging.getLogger('watchfiles').setLevel(logging.WARNING)
    
    # httpx - HTTP客户端
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # openai/anthropic - AI客户端库
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('anthropic').setLevel(logging.WARNING)
    
    # 应用模块 - 可根据需要调整
    logging.getLogger('app.services.ai_service').setLevel(logging.WARNING)
    logging.getLogger('app.api.wizard').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器
    
    Args:
        name: 日志器名称，通常使用 __name__
        
    Returns:
        配置好的日志器实例
    """
    return logging.getLogger(name)