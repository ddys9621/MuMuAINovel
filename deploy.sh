#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[MuMuAINovel] $1"
}

err() {
  echo "[MuMuAINovel] ❌ $1" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "未检测到命令: $1"
    exit 1
  fi
}

log "检查 Docker 环境"
require_cmd docker
require_cmd curl
if ! docker compose version >/dev/null 2>&1; then
  err "未检测到 docker compose 插件，请升级 Docker Desktop"
  exit 1
fi

# embedding 模型预检（必须在 build 之前，避免数分钟构建后才在 entrypoint 报错）
embedding_dir="backend/embedding/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
if [ ! -d "$embedding_dir" ]; then
  cat >&2 <<EOF
================================================================
❌ 缺少 AI 向量模型，无法构建镜像
================================================================

未找到必需的 embedding 模型目录：
  $embedding_dir

获取方式（约 500MB，免费）：

  1. 加入 QQ 交流群：893474348
  2. 在群文件中下载 AI 向量模型压缩包
  3. 解压到 backend/embedding/ 目录，最终结构应为：

       backend/embedding/
       └── models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/
           └── (模型权重和配置文件)

  4. 重新执行 ./deploy.sh

模型文件被 .gitignore 排除，必须手动下载后再构建镜像。
================================================================
EOF
  exit 1
fi

if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    err "缺少 .env.example，无法初始化 .env"
    exit 1
  fi
  cp .env.example .env
  log "已从 .env.example 生成 .env，请按需修改后重新执行"
fi

mkdir -p secrets

if [ ! -f secrets/local_auth_password.txt ]; then
  echo "CHANGE_ME_LOCAL_AUTH_PASSWORD" > secrets/local_auth_password.txt
  err "已生成占位密码文件 secrets/local_auth_password.txt，请编辑为强密码后重新执行"
  exit 1
fi

# 剥离 UTF-8 BOM + 所有空白字符（兼容 Windows Notepad 编辑过的文件）
local_pwd="$(LC_ALL=C sed '1s/^\xef\xbb\xbf//' secrets/local_auth_password.txt | tr -d '[:space:]')"
if [ -z "$local_pwd" ]; then
  err "secrets/local_auth_password.txt 内容为空，请填入强密码"
  exit 1
fi
if [[ "$local_pwd" == CHANGE_ME* ]]; then
  err "检测到默认占位密码，请修改 secrets/local_auth_password.txt 后再部署"
  exit 1
fi

app_port="$(grep -E '^APP_PORT=' .env | tail -n 1 | cut -d'=' -f2- | tr -d '\r\n\"' || true)"
app_port="${app_port:-8000}"
health_url="http://localhost:${app_port}/health/ready"

log "启动容器（首次构建可能需要 5-10 分钟）"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

log "等待服务就绪检查（最多 60 秒）"
for _ in {1..30}; do
  if curl -fsS "$health_url" >/dev/null 2>&1; then
    log "✅ 部署成功，访问地址: http://localhost:${app_port}"
    exit 0
  fi
  sleep 2
done

err "服务未在预期时间内就绪"
echo "请执行以下命令排查：" >&2
echo "  docker compose logs -f mumuainovel" >&2
exit 1
