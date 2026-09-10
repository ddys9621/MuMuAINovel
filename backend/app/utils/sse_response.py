"""Server-Sent Events (SSE) 响应工具类"""
import json
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi.responses import StreamingResponse
from app.logger import get_logger

logger = get_logger(__name__)


class SSEResponse:
    """SSE响应构建器"""
    
    @staticmethod
    def format_sse(data: Dict[str, Any], event: Optional[str] = None) -> str:
        """
        格式化SSE消息
        
        Args:
            data: 要发送的数据字典
            event: 事件类型(可选)
            
        Returns:
            格式化后的SSE消息字符串
        """
        message = ""
        if event:
            message += f"event: {event}\n"
        message += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        return message
    
    @staticmethod
    async def send_progress(
        message: str,
        progress: int,
        status: str = "processing"
    ) -> str:
        """
        发送进度消息
        
        Args:
            message: 进度消息
            progress: 进度百分比(0-100)
            status: 状态(processing/success/error)
        """
        return SSEResponse.format_sse({
            "type": "progress",
            "message": message,
            "progress": progress,
            "status": status
        })
    
    @staticmethod
    async def send_chunk(content: str) -> str:
        """
        发送内容块(用于流式输出AI生成内容)
        
        Args:
            content: 内容块
        """
        return SSEResponse.format_sse({
            "type": "chunk",
            "content": content
        })
    
    @staticmethod
    async def send_result(data: Dict[str, Any]) -> str:
        """
        发送最终结果
        
        Args:
            data: 结果数据
        """
        return SSEResponse.format_sse({
            "type": "result",
            "data": data
        })
    
    @staticmethod
    async def send_error(error: str, code: int = 500) -> str:
        """
        发送错误消息
        
        Args:
            error: 错误描述
            code: 错误码
        """
        return SSEResponse.format_sse({
            "type": "error",
            "error": error,
            "code": code
        })
    
    @staticmethod
    async def send_done() -> str:
        """发送完成消息"""
        return SSEResponse.format_sse({
            "type": "done"
        })
    
    @staticmethod
    async def send_heartbeat() -> str:
        """发送心跳消息(保持连接活跃)"""
        return ": heartbeat\n\n"


def create_sse_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    """
    创建SSE StreamingResponse
    
    Args:
        generator: SSE消息生成器
        
    Returns:
        StreamingResponse对象
    """
    async def wrapper():
        """包装生成器以捕获StreamingResponse初始化时的GeneratorExit"""
        try:
            async for chunk in generator:
                yield chunk
        except GeneratorExit:
            # StreamingResponse在初始化时会进行类型检查，导致GeneratorExit
            # 这是正常行为，不需要记录警告
            pass
    
    return StreamingResponse(
        wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        }
    )