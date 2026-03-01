#!/usr/bin/env bash
set -euo pipefail

if [[ -f data/v2_api.pid ]]; then
  PID="$(cat data/v2_api.pid || true)"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" || true
    echo "Stopped V2 API PID ${PID}"
  else
    echo "V2 API already stopped"
  fi
  rm -f data/v2_api.pid
else
  echo "No pid file"
fi
