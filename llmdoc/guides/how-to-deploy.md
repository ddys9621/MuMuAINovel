# 如何配置和部署项目

本地开发、Docker 部署和桌面打包的操作指南。

## 本地开发

1. **安装依赖：** Python 3.8+、Node.js 16+、PostgreSQL 12+

2. **配置数据库：** 编辑 `backend/.env` 设置 `DATABASE_URL=postgresql+asyncpg://用户:密码@localhost:5432/mumuai_novel`，或编辑根目录 `config.ini`

3. **启动后端：** `cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000`

4. **启动前端：** `cd frontend && npm install && npm run dev`

5. **一键启动（Windows）：** 双击 `双击启动.bat`，自动安装依赖并启动前后端

6. **验证：** 前端 http://localhost:5173，后端 API http://localhost:8000/docs

## Docker 生产部署

1. **准备配置：** `cp .env.example .env`，编辑 `.env` 和 `secrets/*.txt` 设置密码

2. **部署：** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

3. **验证：** 访问 `http://localhost:8000/health` 检查健康状态

## 桌面客户端打包

1. **构建前端：** `cd frontend && npm run build`（产出到 `backend/static/`）

2. **打包 exe：** `cd backend && python -m PyInstaller mumuai.spec`

3. **分发：** 打包后的 exe 通过 `config.ini` 加载外部配置，`start_app.py` 使用 pywebview 提供窗口

