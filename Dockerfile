# 多阶段构建 Dockerfile for AI Story Creator
# 阶段1: 构建前端
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

# 复制前端依赖文件
COPY frontend/package*.json ./

# 使用国内npm镜像加速
RUN npm config set registry https://registry.npmmirror.com

# 安装依赖
RUN npm install

# 复制前端源代码
COPY frontend/ ./

# 临时修改vite配置，使其输出到dist目录（而不是../backend/static）
RUN sed -i "s|outDir: '../backend/static'|outDir: 'dist'|g" vite.config.ts

# 构建前端
RUN npm run build

# 阶段2: 构建最终镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 使用国内镜像源加速
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖并创建非root用户
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && groupadd -r appgroup \
    && useradd -r -g appgroup -d /app -s /usr/sbin/nologin appuser \
    && rm -rf /var/lib/apt/lists/*

# 复制后端依赖文件
COPY backend/requirements.txt ./

# 先从PyTorch官方源安装CPU版本的torch（避免GPU依赖）
RUN pip install --no-cache-dir torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu

# 再安装其他Python依赖（使用阿里云镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制后端代码
COPY backend/ ./

# 从前端构建阶段复制构建好的静态文件
COPY --from=frontend-builder /frontend/dist ./static

# 创建必要的目录并授权
RUN mkdir -p /app/data /app/logs /app/embedding \
    && chown -R appuser:appgroup /app

# 复制预下载的Embedding模型到独立目录（避免被docker-compose的data挂载覆盖）
# 这样可以避免首次运行时联网下载约420MB的模型文件
COPY --chown=appuser:appgroup backend/embedding /app/embedding

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    HF_HUB_OFFLINE=1 \
    SENTENCE_TRANSFORMERS_HOME=/app/embedding

# 使用非root用户运行
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
