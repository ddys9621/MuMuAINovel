# 如何添加新的 API 端点

从后端 API 到前端页面的完整开发流程。

1. **创建/更新数据模型：** 在 `backend/app/models/` 添加 SQLAlchemy 模型，并在 `backend/app/database.py` 的 import 列表中注册

2. **创建 Schema：** 在 `backend/app/schemas/` 添加 Pydantic 请求/响应模型（Create、Update、Response）

3. **创建 API 路由：** 在 `backend/app/api/` 新建路由文件，使用 `APIRouter`，参考 `backend/app/api/world_rules.py` 的结构

4. **注册路由：** 在 `backend/app/main.py` 中 import 并 `app.include_router(xxx.router, prefix="/api")`

5. **前端类型定义：** 在 `frontend/src/types/index.ts` 添加对应的 TypeScript 接口

6. **前端 API 封装：** 在 `frontend/src/services/api.ts` 添加 API 调用方法

7. **验证：** 启动后端，访问 `http://localhost:8000/docs` 查看 Swagger 文档确认端点正常

**重要：** 所有业务 API 需要通过 `get_db()` 注入数据库会话，数据自动按 `user_id` 隔离。

