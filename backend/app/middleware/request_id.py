"""请求追踪ID中间件"""
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求追踪ID中间件
    
    为每个请求生成唯一ID，并添加到日志上下文中
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，添加追踪ID
        
        Args:
            request: 请求对象
            call_next: 下一个处理器
            
        Returns:
            响应对象
        """
        # 从请求头获取追踪ID，或生成新的
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        
        # 将请求ID存储到request.state中，方便后续访问
        request.state.request_id = request_id
        
        # 创建日志过滤器，自动添加request_id到日志记录
        log_filter = RequestIDFilter(request_id)
        
        # 获取根日志器并添加过滤器
        root_logger = logging.getLogger()
        root_logger.addFilter(log_filter)
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 将请求ID添加到响应头
            response.headers['X-Request-ID'] = request_id
            
            return response
        finally:
            # 移除过滤器，避免影响其他请求
            root_logger.removeFilter(log_filter)


class RequestIDFilter(logging.Filter):
    """日志过滤器，为日志记录添加request_id属性"""
    
    def __init__(self, request_id: str):
        """
        初始化过滤器
        
        Args:
            request_id: 请求追踪ID
        """
        super().__init__()
        self.request_id = request_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        为日志记录添加request_id属性
        
        Args:
            record: 日志记录
            
        Returns:
            True（不过滤任何日志）
        """
        record.request_id = self.request_id
        return True