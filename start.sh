#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
CONDA_ENV="${CONDA_ENV:-code_env}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID=""
FRONTEND_PID=""

log() { printf '\033[1;34m[CapitalVoyage]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[CapitalVoyage]\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait "$BACKEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

command -v node >/dev/null 2>&1 || fail "未找到 Node.js，请先安装 Node.js >= 20。"
command -v npm >/dev/null 2>&1 || fail "未找到 npm，请先安装 npm。"
command -v conda >/dev/null 2>&1 || fail "未找到 conda，请确认 Conda 已加入 PATH。"

CONDA_CMD="$(command -v conda)"
if ! "$CONDA_CMD" env list | awk '{print $1}' | grep -Fxq "$CONDA_ENV"; then
  fail "未找到 Conda 环境 $CONDA_ENV；脚本不会创建新环境。"
fi

[[ -d "$BACKEND_DIR" ]] || fail "后端目录不存在：$BACKEND_DIR"
[[ -d "$FRONTEND_DIR" ]] || fail "前端目录不存在：$FRONTEND_DIR"

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "首次运行，正在安装前端依赖……"
  (cd "$FRONTEND_DIR" && npm install)
fi

if ! "$CONDA_CMD" run -n "$CONDA_ENV" python -c 'import fastapi, sqlalchemy, pydantic_settings' >/dev/null 2>&1; then
  log "检测到后端依赖不完整，正在安装 backend[test]……"
  (cd "$ROOT_DIR" && "$CONDA_CMD" run -n "$CONDA_ENV" python -m pip install -e 'backend[test]')
fi

log "启动后端：http://localhost:${BACKEND_PORT}"
(
  cd "$BACKEND_DIR"
  exec "$CONDA_CMD" run --no-capture-output -n "$CONDA_ENV" uvicorn app.main:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload
) &
BACKEND_PID=$!

log "启动前端：http://localhost:${FRONTEND_PORT}"
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

log "前后端已启动，按 Ctrl+C 同时停止。"
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  log "后端进程已退出，正在停止前端。"
else
  log "前端进程已退出，正在停止后端。"
fi

