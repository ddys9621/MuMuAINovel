# 🎭 MuMuAI小说创作工具

> **AI驱动的智能小说创作平台** - 让每个人都能成为小说家

一个专为中文小说创作设计的AI工具，提供角色管理、剧情规划、章节生成等全流程创作支持。无需编程基础，**双击即可使用**！

## ✨ 核心功能

- 🤖 **AI智能创作** - 支持 OpenAI、Claude 等多种AI模型
- 👥 **角色管理** - 智能角色设定、关系图谱、性格分析
- 📖 **剧情规划** - 故事大纲、情节卡片、章节规划
- ✍️ **章节生成** - AI辅助写作、风格定制、内容优化
- 🧠 **记忆系统** - 长期记忆、角色一致性、情节连贯性
- 🔗 **MCP插件** - 扩展AI能力，连接外部工具
- 📊 **可视化** - 关系图谱、剧情时间线、章节结构

## 🚀 一键启动（推荐）

### 系统要求
- **操作系统**: Windows 10/11
- **必备软件**: 
  - Python 3.8+ ([下载地址](https://www.python.org/downloads/))
  - Node.js 16+ ([下载地址](https://nodejs.org/))
  - PostgreSQL 12+ ([下载地址](https://www.postgresql.org/download/windows/))

### 快速开始

1. **下载项目**
   ```
   下载并解压本项目到任意文件夹
   ```

2. **运行一键脚本**
   
   **方法一：双击批处理文件（最简单）**
   - 双击 `双击启动.bat` 文件
   - 系统会自动调用 PowerShell 脚本
   - 无需任何额外设置
   
4. **开始使用**
   - 脚本会自动启动前后端服务
   - 前端地址：http://localhost:5173
   - 后端API：http://localhost:8000
   - API文档：http://localhost:8000/docs
   - 如需配置AI功能，请编辑根目录 `.env` 文件（容器部署）或 `backend/.env` 文件（本地开发）


## 🐳 Docker 生产部署（推荐服务器）

### 1) 准备配置与密钥

```bash
cp .env.example .env
mkdir -p secrets
# 写入强密码（仅一行）
echo "请替换为强密码" > secrets/postgres_password.txt
echo "请替换为强密码" > secrets/local_auth_password.txt
```

Windows 可直接执行：

```powershell
./deploy.ps1
```

Linux/macOS 可执行：

```bash
chmod +x deploy.sh
./deploy.sh
```

> 首次执行会自动检查 Docker / Compose、补齐缺失文件并等待健康检查通过。

### 2) 手动部署命令（等价）

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 3) 常用运维命令

```bash
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f mumuainovel
docker compose logs -f postgres

# 重启服务
docker compose restart mumuainovel

# 停止服务
docker compose down
```

### 4) 升级流程

```bash
# 1. 拉取最新代码
# 2. 按需更新 .env 与 secrets
# 3. 重建并启动
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 5) 回滚流程（快速）

- 使用上一版本代码目录重新执行同样的 `compose up -d --build`。
- 若需回滚数据，请先恢复数据库备份后再启动应用。

### 6) 备份与恢复（PostgreSQL）

备份：

```bash
docker exec -t mumuainovel-postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

恢复：

```bash
cat backup.sql | docker exec -i mumuainovel-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### 7) 排障清单

1. `docker compose ps` 查看是否有容器退出。
2. `docker compose logs -f` 查看报错栈。
3. 检查 `secrets/*.txt` 是否仍是 `CHANGE_ME` 占位值。
4. 检查 `.env` 中端口是否冲突（`APP_PORT` / `POSTGRES_PORT`）。
5. 验证健康检查：`http://localhost:8000/health`。

## 📋 详细安装步骤

如果一键脚本遇到问题，可以按以下步骤手动安装：

### 1. 安装必备软件

#### Python 3.8+
1. 访问 https://www.python.org/downloads/
2. 下载最新版本的Python
3. 安装时勾选"Add Python to PATH"
4. 验证安装：打开命令行输入 `python --version`

#### Node.js 16+
1. 访问 https://nodejs.org/
2. 下载LTS版本
3. 默认安装即可
4. 验证安装：打开命令行输入 `node --version`

#### PostgreSQL 12+
1. 访问 https://www.postgresql.org/download/windows/
2. 下载并安装PostgreSQL
3. 记住设置的超级用户密码
4. 确保安装后 `psql` 命令可用

找到 PostgreSQL 的安装路径（默认类似 C:\Program Files\PostgreSQL\16\bin），将该路径添加到系统环境变量 PATH。
设置方法：开始菜单搜索“环境变量” → 编辑系统环境变量 → 环境变量 → 在“系统变量”里找到 PATH → 编辑 → 新增 PostgreSQL 的 bin 路径 → 保存。

### 2. 配置环境

### 📘 使用 pgAdmin 图形界面创建数据库并配置 `.env`

如果更习惯图形界面，可按以下步骤操作（默认示例：数据库 `mumuai_novel`、用户 `mumuai`、密码 `mumuai123`，可替换成你自己的值）：

1. **准备工作**
   - 确认 PostgreSQL 服务已启动，并能在 pgAdmin 左侧看到本地服务器。
   - 记住超级用户（例如 `postgres`）的登录密码。

2. **创建登录/角色**
   - 在 `Servers -> PostgreSQL 16 -> Login/Group Roles` 上右键，选择 **Create > Login/Group Role...**。
   - `General` 页签填入 `Name = mumuai`。
   - `Definition` 页签设置密码（如 `mumuai123`）。
   - 在 `Privileges` 勾选 `Can login?`，其余保持默认后保存。

3. **创建数据库并指定所有者**
   - 右键 `Servers -> PostgreSQL 16 -> Databases` 选择 **Create > Database...**。
   - `Database = mumuai_novel`，`Owner = mumuai`，`Encoding = UTF8`，保存即可。

4. **授予 schema 权限（推荐）**
   - 右键新数据库选择 **Query Tool**，执行：
     ```sql
     GRANT ALL ON SCHEMA public TO mumuai;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO mumuai;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO mumuai;
     ```

5. **容器部署配置（顶层 `.env`）**
   - 复制根目录 `.env.example` 为 `.env`，并至少设置：
     ```env
     POSTGRES_DB=mumuai_novel
     POSTGRES_USER=mumuai
     POSTGRES_PORT=5432
     DATABASE_URL=postgresql+asyncpg://mumuai:URL_ENCODED_PASSWORD@postgres:5432/mumuai_novel
     ```
   - 密码若包含 `@`、`:`、`/`、`#` 等特殊字符，必须先做 URL 编码。
   - 本项目 Docker 部署密码请通过 `secrets/*.txt` 管理，不建议在 `.env` 明文保存真实密码。


7. **常见故障排查**
   - **认证失败**：确认 `secrets/*.txt` 与 `.env` 配置一致，且不是 `CHANGE_ME` 占位值。
   - **连接被拒绝**：检查 PostgreSQL 服务是否启动、端口是否被占用或防火墙阻断。
   - **权限不足**：确保数据库所有者为目标用户，或重新执行第 4 步的 GRANT 语句。
   - **`DATABASE_URL` 格式错误**：必须以 `postgresql+asyncpg://用户:密码@主机:端口/数据库` 形式书写，且密码需 URL 编码。


### Q: Python 或 Node.js 命令不识别
**A**: 
1. 确认软件已正确安装
2. 重启命令行窗口
3. 检查环境变量PATH设置

### Q: PostgreSQL 连接失败
**A**: 
1. 确认PostgreSQL服务已启动
2. 检查端口5432是否被占用
3. 验证用户名密码是否正确

### Q: 前端页面无法访问
**A**: 
1. 确认后端服务正常运行
2. 检查防火墙是否阻止8000端口
3. 尝试访问 http://127.0.0.1:8000

### Q: AI功能不可用
**A**: 
1. 检查OpenAI API Key是否正确配置
2. 确认API Key有足够余额
3. 检查网络连接是否正常

### Q: 数据库初始化失败
**A**: 
1. 确认PostgreSQL超级用户密码
2. 检查数据库服务是否正常运行
3. 手动创建数据库：
   ```sql
   CREATE DATABASE mumuai_novel;
   CREATE USER mumuai WITH PASSWORD 'your-password';
   GRANT ALL PRIVILEGES ON DATABASE mumuai_novel TO mumuai;
   ```


### API文档
启动后端服务后，访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔐 安全说明

- 默认管理员账号仅用于本地开发
- 生产环境请修改默认密码
- API Key等敏感信息请妥善保管
- 建议定期备份数据库

## 📞 技术支持

如果遇到问题：

1. **查看日志**
   - 后端日志：`backend/logs/app.log`
   - 前端控制台：浏览器F12开发者工具

2. **重置环境**
   ```bash
   # 删除虚拟环境重新安装
   rmdir /s backend\.venv
   rmdir /s frontend\node_modules
   # 重新运行一键脚本
   ```

3. **数据库重置**
   ```sql
   DROP DATABASE IF EXISTS mumuai_novel;
   # 重新运行数据库初始化脚本
   ```

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 📞 联系作者

- 作者QQ：973606500
- 欢迎加入QQ交流群，反馈问题和建议！

## 🙏 致谢

感谢所有贡献者和开源社区的支持！

---

**🎉 开始您的AI小说创作之旅吧！**
