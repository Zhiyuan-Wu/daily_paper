#!/usr/bin/env bash
set -euo pipefail

mkdir -p data

API_HOST="${V2_API_HOST:-127.0.0.1}"
API_PORT="${V2_API_PORT:-8001}"

# stop previous if pid file exists
if [[ -f data/v2_api.pid ]]; then
  OLD_PID="$(cat data/v2_api.pid || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    kill "${OLD_PID}" || true
  fi
fi

nohup python -m uvicorn v2.api.app:app --host "${API_HOST}" --port "${API_PORT}" > data/v2_api.log 2>&1 &
echo $! > data/v2_api.pid

sleep 1

echo "V2 API started at http://${API_HOST}:${API_PORT}"
echo "PID: $(cat data/v2_api.pid)"
