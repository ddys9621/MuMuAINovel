# 编码规范参考

## 1. 核心摘要

项目遵循前后端分离架构，后端 Python（FastAPI）+ 前端 TypeScript（React）。使用 ESLint 进行前端代码检查，后端无显式 linter 配置但遵循 PEP 8 风格。

## 2. 后端规范（Python / FastAPI）

- **框架**：FastAPI + async/await 异步编程
- **ORM**：SQLAlchemy 2.0 异步模式，所有数据库操作使用 `AsyncSession`
- **数据验证**：Pydantic v2 BaseModel 用于请求/响应 Schema
- **配置管理**：pydantic-settings BaseSettings 从 `.env` 加载配置
- **日志**：统一使用 `app.logger.get_logger(__name__)` 获取 logger
- **API 路由**：使用 `APIRouter`，统一 `/api` 前缀
- **依赖注入**：`get_db()` 注入数据库会话，Request 对象提供 user_id
- **错误处理**：自定义 `app/exceptions.py`，全局异常处理器在 `main.py`
- **命名风格**：文件名 snake_case，类名 PascalCase，函数/变量 snake_case

## 3. 前端规范（TypeScript / React）

- **框架**：React 18 + TypeScript（strict 模式）
- **构建**：Vite 5
- **状态管理**：Zustand（单 store，见 `store/index.ts`）
- **UI 组件库**：Ant Design 5，中文 locale（zhCN）
- **路由**：React Router DOM v6，嵌套路由
- **HTTP 客户端**：Axios（`services/api.ts`），3 分钟超时，withCredentials
- **SSE 客户端**：自定义 `utils/sseClient.ts`，POST 模式
- **ESLint**：`eslint.config.js` 配置了 react-hooks 和 react-refresh 插件
- **命名风格**：文件名 PascalCase（组件）或 camelCase（工具），接口 PascalCase

## 4. 通用规范

- **数据隔离**：所有业务数据模型包含 `user_id` 字段，查询自动过滤
- **SSE 流式**：所有 AI 生成操作使用 Server-Sent Events 流式返回
- **多语言 UI**：界面中文，代码注释中文为主
- **配置层级**：`.env`（开发）→ `config.ini`（桌面版）→ 环境变量（Docker）

## 5. 信息来源

- **后端入口**：`backend/app/main.py`
- **前端 ESLint**：`frontend/eslint.config.js`
- **TypeScript 配置**：`frontend/tsconfig.json`, `frontend/tsconfig.app.json`
- **Vite 配置**：`frontend/vite.config.ts`
- **Python 依赖**：`backend/requirements.txt`
- **Node 依赖**：`frontend/package.json`

