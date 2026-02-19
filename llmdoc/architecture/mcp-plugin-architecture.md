# MCP 插件系统架构

## 1. 身份

- **是什么：** Model Context Protocol (MCP) 插件注册、管理和调用系统
- **目的：** 扩展 AI 的能力边界，连接外部工具和数据源，增强创作辅助

## 2. 核心组件

- `backend/app/mcp/registry.py` (MCPRegistry): 插件注册中心，管理插件生命周期和后台任务
- `backend/app/mcp/config.py`: MCP 配置管理
- `backend/app/mcp/http_client.py`: MCP HTTP 客户端，与外部 MCP 服务通信
- `backend/app/models/mcp_plugin.py` (MCPPlugin): 插件数据模型（名称、配置JSON、启用状态）
- `backend/app/services/mcp_tool_service.py` (MCPToolService): MCP 工具调用服务
- `backend/app/services/mcp_test_service.py` (MCPTestService): 插件连接测试服务
- `backend/app/api/mcp_plugins.py`: 插件管理 API
- `frontend/src/pages/MCPPlugins.tsx`: 插件管理页面
- `frontend/src/components/MCPSelector.tsx`: 插件选择器组件
- `frontend/src/components/MCPEnhancedForm.tsx`: 增强的 MCP 表单

## 3. 执行流程

- **1. 注册插件：** 用户通过界面配置 MCP 插件（JSON 配置），存入数据库
- **2. 启动连接：** 应用启动时 `mcp_registry._start_background_tasks()` 初始化后台任务
- **3. 工具发现：** MCPRegistry 从已启用的插件发现可用工具列表
- **4. 工具调用：** AI 生成过程中按需调用 MCP 工具，通过 HTTP 客户端与外部服务通信
- **5. 清理：** 应用关闭时 `mcp_registry.cleanup_all()` 清理所有插件连接

## 4. 设计原理

- **JSON 配置**：插件使用 `config_json` 字段存储灵活的配置，适应不同 MCP 服务的参数需求
- **后台任务**：插件连接管理在后台异步执行，不阻塞主应用
- **测试服务**：提供独立的 MCPTestService，用户可在保存前验证插件配置是否有效

