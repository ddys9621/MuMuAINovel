# AI 服务系统架构

## 1. 身份

- **是什么：** 统一的多模型 AI 调用接口，支持 OpenAI / Anthropic / Gemini 兼容 API
- **目的：** 为章节生成、角色生成、剧情规划等所有 AI 功能提供标准化的流式/非流式调用能力

## 2. 核心组件

- `backend/app/services/ai_service.py` (AIService): 核心 AI 客户端封装，单例管理，支持 OpenAI 和 Anthropic 双客户端
- `backend/app/config.py` (Settings): AI 相关配置项（api_key, base_url, model, temperature, max_tokens）
- `backend/app/api/settings.py`: 用户运行时设置 API（可覆盖全局 AI 配置）
- `backend/app/models/settings.py` (Settings model): 用户级 AI 设置的数据库持久化

## 3. 执行流程

- **1. 客户端初始化：** `AIService.__init__` 根据配置创建 `AsyncOpenAI` 和 `AsyncAnthropic` 客户端，配置连接池（100 连接 / 50 keep-alive）
- **2. 设置加载：** 每次 API 请求时，从数据库加载用户级设置 → 若用户有自定义设置则用用户设置创建临时 AIService，否则使用全局 `ai_service` 单例
- **3. 流式生成：** 调用 `stream_chat()` 方法，返回 `AsyncGenerator[str]`，通过 SSE 推送到前端
- **4. 非流式生成：** 调用 `chat()` 方法，一次性返回完整结果
- **5. 资源清理：** 应用关闭时 `lifespan` 调用 `ai_service.close()` 关闭 HTTP 客户端

## 4. 设计原理

- **双客户端架构**：同时维护 OpenAI 和 Anthropic 客户端实例，按 `api_provider` 字段分发
- **用户级覆盖**：全局配置 → 用户设置覆盖，每次请求动态决定使用哪个配置
- **高并发优化**：使用 `httpx.AsyncClient` 自定义连接池参数，支持 80-150 并发用户
- **超时策略**：connect=60s, read=180s, write=60s, pool=60s（适应大模型长时间生成）

