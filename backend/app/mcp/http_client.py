"""HTTP MCP客户端 - 使用官方 MCP Python SDK 实现"""
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client
from pydantic import AnyUrl

from app.logger import get_logger

logger = get_logger(__name__)


class MCPError(Exception):
    """MCP错误"""
    pass


class HTTPMCPClient:
    """HTTP模式MCP客户端（基于官方 MCP Python SDK）"""
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0
    ):
        """
        初始化HTTP MCP客户端
        
        Args:
            url: MCP服务器URL
            headers: HTTP请求头
            env: 环境变量（用于API Key等）
            timeout: 超时时间（秒）
        """
        self.url = url.rstrip('/')
        self.headers = headers or {}
        self.env = env or {}
        self.timeout = timeout
        
        # 如果env中有API Key，添加到headers
        if 'API_KEY' in self.env:
            self.headers['Authorization'] = f'Bearer {self.env["API_KEY"]}'
        
        self._session: Optional[ClientSession] = None
        self._context_stack = []  # 保存上下文管理器栈
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def _ensure_connected(self):
        """确保连接已建立"""
        async with self._lock:
            if self._session is None:
                try:
                    logger.info(f"🔗 连接到MCP服务器: {self.url}")
                    
                    # 使用官方 SDK 的 streamable_http_client
                    # 保存上下文管理器以便后续正确清理
                    stream_context = streamablehttp_client(self.url)
                    read_stream, write_stream, _ = await stream_context.__aenter__()
                    self._context_stack.append(('stream', stream_context))
                    
                    # 创建客户端会话
                    self._session = ClientSession(read_stream, write_stream)
                    session_context = self._session
                    await session_context.__aenter__()
                    self._context_stack.append(('session', session_context))
                    
                    # 初始化会话
                    await self._session.initialize()
                    self._initialized = True
                    
                    logger.info(f"✅ MCP会话初始化成功")
                    
                except Exception as e:
                    logger.error(f"❌ MCP连接失败: {e}")
                    await self._cleanup()
                    raise MCPError(f"连接MCP服务器失败: {str(e)}")
    
    async def _cleanup(self):
        """清理连接资源（按照进入的相反顺序退出）"""
        # 按照LIFO顺序清理上下文
        while self._context_stack:
            ctx_type, ctx = self._context_stack.pop()
            try:
                await ctx.__aexit__(None, None, None)
            except RuntimeError as e:
                # 忽略 anyio 的任务上下文错误（在关闭时可能发生）
                if "cancel scope" in str(e).lower() or "different task" in str(e).lower():
                    logger.debug(f"忽略{ctx_type}上下文清理的任务切换警告: {e}")
                else:
                    logger.error(f"清理{ctx_type}上下文失败: {e}")
            except Exception as e:
                logger.error(f"清理{ctx_type}上下文失败: {e}")
        
        self._session = None
        self._initialized = False
    
    async def initialize(self) -> Dict[str, Any]:
        """
        初始化MCP会话
        
        Returns:
            初始化响应
        """
        await self._ensure_connected()
        return {"status": "initialized"}
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列举可用工具
        
        Returns:
            工具列表
        """
        try:
            await self._ensure_connected()
            
            result = await self._session.list_tools()
            
            # 转换为字典格式
            tools = []
            for tool in result.tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema
                }
                tools.append(tool_dict)
            
            logger.info(f"获取到 {len(tools)} 个工具")
            return tools
            
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            raise MCPError(f"获取工具列表失败: {str(e)}")
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            await self._ensure_connected()
            
            logger.info(f"调用工具: {tool_name}")
            logger.debug(f"参数: {arguments}")
            
            result = await self._session.call_tool(tool_name, arguments)
            
            # 处理返回结果
            # MCP SDK 返回 CallToolResult 对象
            if result.content:
                # 提取第一个content的文本
                for content in result.content:
                    if isinstance(content, types.TextContent):
                        return content.text
                    elif isinstance(content, types.ImageContent):
                        return {
                            "type": "image",
                            "data": content.data,
                            "mimeType": content.mimeType
                        }
                # 如果没有文本内容，返回原始内容
                return result.content[0] if result.content else None
            
            # 如果有结构化内容（2025-06-18规范）
            if hasattr(result, 'structuredContent') and result.structuredContent:
                return result.structuredContent
            
            return None
            
        except Exception as e:
            logger.error(f"调用工具失败: {tool_name}, 错误: {e}")
            raise MCPError(f"调用工具失败: {str(e)}")
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        列举可用资源
        
        Returns:
            资源列表
        """
        try:
            await self._ensure_connected()
            
            result = await self._session.list_resources()
            
            # 转换为字典格式
            resources = []
            for resource in result.resources:
                resource_dict = {
                    "uri": str(resource.uri),
                    "name": resource.name,
                    "description": resource.description or "",
                    "mimeType": resource.mimeType or ""
                }
                resources.append(resource_dict)
            
            logger.info(f"获取到 {len(resources)} 个资源")
            return resources
            
        except Exception as e:
            logger.error(f"获取资源列表失败: {e}")
            raise MCPError(f"获取资源列表失败: {str(e)}")
    
    async def read_resource(self, uri: str) -> Any:
        """
        读取资源
        
        Args:
            uri: 资源URI
            
        Returns:
            资源内容
        """
        try:
            await self._ensure_connected()
            
            result = await self._session.read_resource(AnyUrl(uri))
            
            # 提取资源内容
            if result.contents:
                content = result.contents[0]
                if isinstance(content, types.TextContent):
                    return content.text
                elif isinstance(content, types.ImageContent):
                    return {
                        "type": "image",
                        "data": content.data,
                        "mimeType": content.mimeType
                    }
                elif isinstance(content, types.BlobResourceContents):
                    return {
                        "type": "blob",
                        "blob": content.blob,
                        "mimeType": content.mimeType
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"读取资源失败: {uri}, 错误: {e}")
            raise MCPError(f"读取资源失败: {str(e)}")
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            测试结果
        """
        import time
        start_time = time.time()
        
        try:
            # 尝试连接并列举工具（直接调用SDK，避免重复日志）
            await self._ensure_connected()
            
            result = await self._session.list_tools()
            
            # 转换为字典格式
            tools = []
            for tool in result.tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema
                }
                tools.append(tool_dict)
            
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)
            
            logger.info(f"✅ 连接测试成功，获取到 {len(tools)} 个工具")
            
            return {
                "success": True,
                "message": "连接测试成功",
                "response_time_ms": response_time,
                "tools_count": len(tools),
                "tools": tools
            }
            
        except Exception as e:
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)
            
            return {
                "success": False,
                "message": "连接测试失败",
                "response_time_ms": response_time,
                "error": str(e),
                "error_type": type(e).__name__,
                "suggestions": [
                    "请检查服务器URL是否正确",
                    "请确认API Key是否有效",
                    "请检查网络连接",
                    "请确认MCP服务器是否在线"
                ]
            }
    
    async def close(self):
        """关闭客户端连接"""
        logger.info(f"关闭MCP客户端: {self.url}")
        await self._cleanup()


@asynccontextmanager
async def create_mcp_client(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 60.0
):
    """
    创建MCP客户端的上下文管理器
    
    Args:
        url: MCP服务器URL
        headers: HTTP请求头
        env: 环境变量
        timeout: 超时时间
        
    Yields:
        HTTPMCPClient实例
    """
    client = HTTPMCPClient(url, headers, env, timeout)
    try:
        await client.initialize()
        yield client
    finally:
        await client.close()