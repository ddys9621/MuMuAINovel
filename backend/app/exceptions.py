"""自定义异常类"""


class MCPToolNotTriggeredError(Exception):
    """MCP 工具未被触发异常
    
    当启用 MCP 但工具未被 AI 调用时抛出此异常。
    可能原因：
    1. 选择的插件不适用于当前任务
    2. AI 判断不需要使用工具
    3. 工具配置错误
    """
    pass


class MCPPlanningFailedError(Exception):
    """MCP 规划阶段失败异常
    
    当 MCP 规划阶段发生错误时抛出此异常。
    """
    pass
