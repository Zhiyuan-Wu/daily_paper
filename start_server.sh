#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT_DIR/data}"
mkdir -p "$DATA_DIR"

# Backend config
BACKEND_APP="${BACKEND_APP:-v2.api.app:app}"
BACKEND_HOST="${BACKEND_HOST:-${V2_API_HOST:-0.0.0.0}}"
BACKEND_PORT="${BACKEND_PORT:-${V2_API_PORT:-8011}}"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-$DATA_DIR/v2_api.pid}"
BACKEND_LOG_FILE="${BACKEND_LOG_FILE:-$DATA_DIR/v2_api.log}"

# Frontend config
FRONTEND_ENABLE="${FRONTEND_ENABLE:-1}"
FRONTEND_DIR="${FRONTEND_DIR:-$ROOT_DIR/frontend}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5183}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-$DATA_DIR/frontend.pid}"
FRONTEND_LOG_FILE="${FRONTEND_LOG_FILE:-$DATA_DIR/frontend.log}"
NPM_BIN="${NPM_BIN:-npm}"
FRONTEND_INSTALL_DEPS="${FRONTEND_INSTALL_DEPS:-1}"

abort_startup() {
  local reason="$1"
  echo "$reason"
  if [[ -f "$BACKEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$BACKEND_PID_FILE" || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      sleep 0.3
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" || true
      fi
      echo "Backend rolled back due to startup failure (PID $pid)"
    fi
  fi
  exit 1
}

stop_if_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      kill "$old_pid" || true
      sleep 0.5
    fi
  fi
}

start_backend() {
  stop_if_running "$BACKEND_PID_FILE"

  nohup python -m uvicorn "$BACKEND_APP" \
    --host "$BACKEND_HOST" \
    --port "$BACKEND_PORT" \
    > "$BACKEND_LOG_FILE" 2>&1 &

  echo $! > "$BACKEND_PID_FILE"
  sleep 1
  local pid
  pid="$(cat "$BACKEND_PID_FILE")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "Backend failed to start. Check log: $BACKEND_LOG_FILE"
    exit 1
  fi

  echo "Backend started: http://$BACKEND_HOST:$BACKEND_PORT"
  echo "  PID: $pid"
  echo "  Log: $BACKEND_LOG_FILE"
}

start_frontend() {
  if [[ "$FRONTEND_ENABLE" != "1" ]]; then
    echo "Frontend disabled (FRONTEND_ENABLE=$FRONTEND_ENABLE)"
    return 0
  fi

  if [[ ! -d "$FRONTEND_DIR" ]]; then
    abort_startup "Frontend directory not found: $FRONTEND_DIR"
  fi

  if ! command -v "$NPM_BIN" >/dev/null 2>&1; then
    abort_startup "npm not found (NPM_BIN=$NPM_BIN)"
  fi

  stop_if_running "$FRONTEND_PID_FILE"

  if [[ "$FRONTEND_INSTALL_DEPS" == "1" ]] && [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Installing frontend dependencies in $FRONTEND_DIR ..."
    (
      cd "$FRONTEND_DIR"
      "$NPM_BIN" install
    )
  fi

  (
    cd "$FRONTEND_DIR"
    nohup "$NPM_BIN" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
      > "$FRONTEND_LOG_FILE" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )

  sleep 1
  local pid
  pid="$(cat "$FRONTEND_PID_FILE")"
  if ! kill -0 "$pid" 2>/dev/null; then
    abort_startup "Frontend failed to start. Check log: $FRONTEND_LOG_FILE"
  fi

  echo "Frontend started: http://$FRONTEND_HOST:$FRONTEND_PORT"
  echo "  PID: $pid"
  echo "  Log: $FRONTEND_LOG_FILE"
}

start_backend
start_frontend

echo "All requested services started."
