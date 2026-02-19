# Git 规范参考

## 1. 核心摘要

项目使用 Git 进行版本控制。由于未检测到 git log 历史记录，以下为推荐的 Git 规范。

## 2. 推荐提交格式

采用 Conventional Commits 风格：

```
<type>(<scope>): <subject>

<body>
```

### Type 列表

| Type | 描述 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（非新功能、非修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖变更 |

### Scope 建议

| Scope | 对应模块 |
|-------|---------|
| `backend` | 后端整体 |
| `frontend` | 前端整体 |
| `ai` | AI 服务相关 |
| `plot` | 剧情系统 |
| `chapter` | 章节系统 |
| `character` | 角色系统 |
| `memory` | 记忆系统 |
| `mcp` | MCP 插件 |
| `auth` | 认证系统 |
| `db` | 数据库/迁移 |
| `deploy` | 部署相关 |

### 示例

```
feat(plot): 添加剧情卡片批量排序功能
fix(memory): 修复 ChromaDB 语义检索超时问题
refactor(ai): 统一 OpenAI 和 Anthropic 客户端初始化逻辑
```

## 3. 分支策略

- `main`：稳定发布分支
- `dev`：开发分支
- `feature/*`：功能分支
- `fix/*`：修复分支

## 4. 信息来源

- **项目根目录**：`.gitignore`（如存在）
- **部署脚本**：`deploy.ps1`, `deploy.sh`
- **打包脚本**：`pack_release.ps1`, `backend/build_exe.ps1`

