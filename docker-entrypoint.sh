#!/bin/sh
set -eu

# 从 *_FILE 环境变量指向的文件读取 secret 值并导出对应变量。
# 兼容 Windows Notepad 编辑过的密码文件：剥离 UTF-8 BOM、CR/LF、所有空白字符。
read_secret() {
  var_name="$1"
  file_var="${var_name}_FILE"
  eval "file_path=\${$file_var:-}"

  if [ -n "$file_path" ] && [ -f "$file_path" ]; then
    value="$(LC_ALL=C sed '1s/^\xef\xbb\xbf//' "$file_path" | tr -d '[:space:]')"
    export "$var_name=$value"
  fi
}

read_secret LOCAL_AUTH_PASSWORD

: "${DATABASE_URL:=sqlite+aiosqlite:///./data/mumuai.db}"
export DATABASE_URL

if [ "${LOCAL_AUTH_ENABLED:-true}" != "false" ] && [ -z "${LOCAL_AUTH_PASSWORD:-}" ]; then
  cat >&2 <<'EOF'
================================================================
[MuMuAINovel] ❌ 本地账户密码未配置
================================================================

LOCAL_AUTH_ENABLED=true，但未读取到 LOCAL_AUTH_PASSWORD。

请检查：
  1. secrets/local_auth_password.txt 是否存在且非空
  2. 文件内容是否仅包含密码（无多余空行）
  3. 如不需要本地账户，请在 .env 中设置 LOCAL_AUTH_ENABLED=false

================================================================
EOF
  exit 1
fi

required_embedding_dir="/app/embedding/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
if [ ! -d "$required_embedding_dir" ]; then
  cat >&2 <<'EOF'
================================================================
[MuMuAINovel] ❌ 缺少 AI 向量模型，容器无法启动
================================================================

容器内未找到必需的 embedding 模型：
  /app/embedding/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/

获取方式（约 500MB，免费）：

  1. 加入 QQ 交流群：893474348
  2. 在群文件中下载 AI 向量模型压缩包
  3. 解压到主机的 backend/embedding/ 目录，最终结构应为：

       backend/embedding/
       └── models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/
           └── (模型权重和配置文件)

  4. 重新执行 ./deploy.sh 或 docker compose up -d --build

注意：模型文件被 .gitignore 排除，必须手动下载后再构建镜像。
================================================================
EOF
  exit 1
fi

mkdir -p /app/data /app/logs

exec "$@"
