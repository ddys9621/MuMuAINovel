# 认证与用户系统架构

## 1. 身份

- **是什么：** 双模式认证系统，支持本地账户登录和 LinuxDO OAuth2 第三方登录
- **目的：** 提供灵活的用户身份验证，本地开发零配置即用，生产环境支持 OAuth2

## 2. 核心组件

- `backend/app/middleware/auth_middleware.py` (AuthMiddleware): 认证中间件，拦截所有请求验证身份
- `backend/app/api/auth.py`: 认证 API（登录、登出、回调、会话刷新）
- `backend/app/services/oauth_service.py` (OAuthService): LinuxDO OAuth2 服务封装
- `backend/app/models/user.py` (User): 用户模型
- `backend/app/user_manager.py`: 用户管理工具
- `backend/app/user_password.py`: 密码工具
- `backend/app/api/users.py`: 用户信息 API
- `backend/app/api/admin.py`: 管理员 API（用户管理）
- `frontend/src/pages/Login.tsx`: 登录页面
- `frontend/src/pages/AuthCallback.tsx`: OAuth2 回调页面
- `frontend/src/components/ProtectedRoute.tsx`: 路由守卫组件
- `frontend/src/utils/sessionManager.ts`: 前端会话管理

## 3. 执行流程

### 本地账户登录
- **1.** 用户在登录页输入用户名密码
- **2.** 后端 `auth.py` 验证凭据（对比 config.ini 或 .env 中的配置）
- **3.** 验证通过后创建会话，设置 Cookie
- **4.** AuthMiddleware 在后续请求中验证会话有效性

### LinuxDO OAuth2 登录
- **1.** 前端跳转到 LinuxDO 授权页面
- **2.** 用户授权后回调到 `/api/auth/callback`
- **3.** OAuthService 用授权码换取 access_token，获取用户信息
- **4.** 自动创建/更新本地用户记录，建立会话

### 会话管理
- **会话过期**：默认 2 小时（`SESSION_EXPIRE_MINUTES=120`）
- **自动刷新**：剩余时间 < 30 分钟时可刷新（`SESSION_REFRESH_THRESHOLD_MINUTES=30`）
- **前端守卫**：`ProtectedRoute` 组件检查登录状态，未登录重定向到 `/login`

## 4. 设计原理

- **双模式**：`LOCAL_AUTH_ENABLED=true` 启用本地登录，可与 OAuth2 共存
- **中间件拦截**：AuthMiddleware 统一处理认证，白名单路径（/health, /api/auth/*, /docs）免认证
- **数据隔离**：所有业务数据通过 `user_id` 字段实现多用户数据隔离
- **管理员角色**：通过 `INITIAL_ADMIN_LINUXDO_ID` 指定初始管理员

