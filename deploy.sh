#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[MuMuAINovel] $1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "未检测到命令: $1" >&2
    exit 1
  fi
}

log "检查 Docker 环境"
require_cmd docker
require_cmd curl
if ! docker compose version >/dev/null 2>&1; then
  echo "未检测到 docker compose 插件" >&2
  exit 1
fi

if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    echo "缺少 .env.example，无法初始化 .env" >&2
    exit 1
  fi
  cp .env.example .env
  log "已从 .env.example 生成 .env，请按需修改"
fi

mkdir -p secrets

if [ ! -f secrets/local_auth_password.txt ]; then
  echo "CHANGE_ME_LOCAL_AUTH_PASSWORD" > secrets/local_auth_password.txt
  echo "请编辑 secrets/local_auth_password.txt 为强密码"
fi

local_pwd="$(tr -d '\r\n' < secrets/local_auth_password.txt)"
if [[ "$local_pwd" == CHANGE_ME* ]]; then
  echo "检测到默认占位密码，请先修改 secrets/*.txt 后再部署" >&2
  exit 1
fi

app_port="$(grep -E '^APP_PORT=' .env | tail -n 1 | cut -d'=' -f2- | tr -d '\r\n\"' || true)"
app_port="${app_port:-8000}"
health_url="http://localhost:${app_port}/health/ready"

log "启动容器"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

log "等待服务就绪检查"
for _ in {1..30}; do
  if curl -fsS "$health_url" >/dev/null 2>&1; then
    echo "部署成功，访问地址: http://localhost:${app_port}"
    exit 0
  fi
  sleep 2
done

echo "服务未在预期时间内就绪，请执行 docker compose logs -f 查看日志" >&2
exit 1
