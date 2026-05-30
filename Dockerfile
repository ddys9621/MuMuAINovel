# 多阶段构建 Dockerfile for MuMuAINovel
#
# 镜像源可通过 build args 覆盖，方便国内/海外环境切换：
#   docker build --build-arg NPM_REGISTRY=https://registry.npmjs.org \
#                --build-arg PIP_INDEX_URL=https://pypi.org/simple/ \
#                --build-arg DEBIAN_MIRROR= ...
# DEBIAN_MIRROR 留空则保留官方源。

# ---------- 阶段1: 构建前端 ----------
FROM node:22-alpine AS frontend-builder

ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /frontend

COPY frontend/package*.json ./

RUN npm config set registry "$NPM_REGISTRY" \
    && npm install

COPY frontend/ ./

# vite.config.ts 内置 DOCKER_BUILD 判断，输出到 dist 而非 ../backend/static
ENV DOCKER_BUILD=1
RUN npm run build

# ---------- 阶段2: 构建最终镜像 ----------
FROM python:3.11-slim

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG DEBIAN_MIRROR=mirrors.aliyun.com

WORKDIR /app

# 切换 Debian 镜像源加速 apt（DEBIAN_MIRROR 为空则保留官方源）
RUN if [ -n "$DEBIAN_MIRROR" ] && [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g; s|security.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi

# 安装系统依赖并创建非 root 用户
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && groupadd -r appgroup \
    && useradd -r -g appgroup -d /app -s /usr/sbin/nologin appuser \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单（独立层，便于缓存复用）
COPY backend/requirements.txt ./

# 先从 PyTorch 官方源安装 CPU 版本（避免 GPU 依赖与镜像源不一致）
RUN pip install --no-cache-dir torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu

# 安装应用 Python 依赖（默认走国内镜像，可通过 PIP_INDEX_URL 覆盖）
RUN pip install --no-cache-dir -r requirements.txt -i "$PIP_INDEX_URL"

# 复制后端代码、前端产物、入口脚本，全部直接指定 owner=appuser，
# 避免后续 chown -R /app 把整个镜像层（含 site-packages、torch、embedding）翻倍复制。
COPY --chown=appuser:appgroup backend/ ./
COPY --from=frontend-builder --chown=appuser:appgroup /frontend/dist ./static
COPY --chown=appuser:appgroup docker-entrypoint.sh ./docker-entrypoint.sh

# 仅对运行时实际写入的目录授权（site-packages 由 root 拥有 + 默认 0644 全员可读，appuser 只读够用）
RUN mkdir -p /app/data /app/logs /app/embedding \
    && chmod +x /app/docker-entrypoint.sh \
    && chown appuser:appgroup /app/data /app/logs /app/embedding

ENV PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    HF_HUB_OFFLINE=1 \
    SENTENCE_TRANSFORMERS_HOME=/app/embedding

USER appuser

EXPOSE 8000

# 健康检查由 docker-compose.yml 统一管理（DRY，避免双处维护不同步）

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
