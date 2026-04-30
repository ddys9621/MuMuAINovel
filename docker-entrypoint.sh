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

generate_database_url() {
  python - <<'PY'
import os
from urllib.parse import quote

required = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"]
missing = [name for name in required if not os.environ.get(name)]
if missing:
    raise SystemExit("missing database settings: " + ", ".join(missing))

user = quote(os.environ["POSTGRES_USER"], safe="")
password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
host = os.environ["POSTGRES_HOST"]
port = os.environ["POSTGRES_PORT"]
database = quote(os.environ["POSTGRES_DB"], safe="")

print(f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}")
PY
}

read_secret POSTGRES_PASSWORD
read_secret LOCAL_AUTH_PASSWORD

case "${DATABASE_URL:-}" in
  ""|*REPLACE_WITH_URLENCODED_PASSWORD*|*your_secure_password_here*)
    DATABASE_URL="$(generate_database_url)"
    export DATABASE_URL
    ;;
esac

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
