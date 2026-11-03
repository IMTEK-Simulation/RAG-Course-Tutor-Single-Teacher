#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt

exec .venv/bin/uvicorn backend.main:app \
  --host "${RAG_TUTOR_HOST:-127.0.0.1}" \
  --port "${RAG_TUTOR_PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips "127.0.0.1"
