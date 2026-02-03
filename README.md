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
   - 如需配置AI功能，请编辑 `backend\.env` 文件


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

5. **配置 `backend/.env`**
   - 将 `backend/.env.example` 复制为 `.env`，并至少设置：
     ```env
     POSTGRES_DB=mumuai_novel
     POSTGRES_USER=mumuai
     POSTGRES_PASSWORD=mumuai123
     POSTGRES_PORT=5432
     DATABASE_URL=postgresql+asyncpg://mumuai:mumuai123@localhost:5432/mumuai_novel
     ```
   - 如果数据库部署在远程服务器，替换 `localhost` 与端口即可。


7. **常见故障排查**
   - **认证失败**：确认 `.env` 中的用户名/密码与步骤 2 设置的一致。
   - **连接被拒绝**：检查 PostgreSQL 服务是否启动、端口是否被占用或防火墙阻断。
   - **权限不足**：确保数据库所有者为目标用户，或重新执行第 4 步的 GRANT 语句。
   - **`DATABASE_URL` 格式错误**：必须以 `postgresql+asyncpg://用户:密码@主机:端口/数据库` 形式书写。


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
