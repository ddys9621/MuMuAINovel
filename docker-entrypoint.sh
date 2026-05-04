#!/bin/sh
set -eu

read_secret() {
  var_name="$1"
  file_var="${var_name}_FILE"
  eval "file_path=\${$file_var:-}"

  if [ -n "$file_path" ] && [ -f "$file_path" ]; then
    value="$(tr -d '\r\n' < "$file_path")"
    export "$var_name=$value"
  fi
}

read_secret LOCAL_AUTH_PASSWORD

: "${DATABASE_URL:=sqlite+aiosqlite:///./data/mumuai.db}"
export DATABASE_URL

if [ "${LOCAL_AUTH_ENABLED:-true}" != "false" ] && [ -z "${LOCAL_AUTH_PASSWORD:-}" ]; then
  echo "LOCAL_AUTH_PASSWORD is required when local auth is enabled." >&2
  exit 1
fi

required_embedding_dir="/app/embedding/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
if [ ! -d "$required_embedding_dir" ]; then
  echo "Missing offline embedding model: $required_embedding_dir" >&2
  echo "Prepare backend/embedding before building the Docker image." >&2
  exit 1
fi

mkdir -p /app/data /app/logs

exec "$@"
