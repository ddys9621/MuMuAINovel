"""MCP插件Pydantic模式"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class MCPToolSchema(BaseModel):
    """MCP工具定义"""
    name: str
    description: Optional[str] = None
    inputSchema: Optional[Dict[str, Any]] = None
    category: Optional[str] = None


class MCPPluginBase(BaseModel):
    """插件基础模式"""
    plugin_name: str = Field(..., description="插件唯一标识")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="插件描述")
    plugin_type: str = Field(default="http", description="插件类型：http/stdio")
    category: str = Field(default="general", description="分类")
    sort_order: int = Field(default=0, description="排序顺序")


class MCPPluginCreate(MCPPluginBase):
    """创建插件"""
    server_url: Optional[str] = Field(None, description="服务器URL（HTTP类型）")
    command: Optional[str] = Field(None, description="启动命令（stdio类型）")
    args: Optional[List[str]] = Field(None, description="命令参数")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP请求头")
    config: Optional[Dict[str, Any]] = Field(None, description="插件特定配置")
    enabled: bool = Field(default=True, description="是否启用")


class MCPPluginSimpleCreate(BaseModel):
    """简化的插件创建（通过标准MCP配置JSON）"""
    config_json: str = Field(..., description="标准MCP配置JSON字符串")
    enabled: bool = Field(default=True, description="是否启用")
    category: str = Field(default="general", description="插件分类")


class MCPPluginUpdate(BaseModel):
    """更新插件"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    server_url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    category: Optional[str] = None
    sort_order: Optional[int] = None


class MCPPluginResponse(BaseModel):
    """插件响应 - 优化后只返回必要字段"""
    id: str
    plugin_name: str
    display_name: str
    description: Optional[str] = None
    plugin_type: str
    category: str
    
    # HTTP类型字段
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # Stdio类型字段
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # 状态字段
    enabled: bool
    status: str
    last_error: Optional[str] = None
    last_test_at: Optional[datetime] = None
    
    # 时间戳
    created_at: datetime

    class Config:
        from_attributes = True


class MCPToolCall(BaseModel):
    """工具调用请求"""
    plugin_id: str = Field(..., description="插件ID")
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")


class MCPTestResult(BaseModel):
    """测试结果"""
    success: bool
    message: str
    response_time_ms: Optional[float] = None
    tools_count: Optional[int] = None
    tools: Optional[List[MCPToolSchema]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    suggestions: Optional[List[str]] = None