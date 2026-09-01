#!/usr/bin/env bash
# Update the production checkout, rebuild the web UI, and restart the API.
# Run this script as root from /srv/capitalvoyage (or any directory).
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_USER="${DEPLOY_USER:-capitalvoyage}"
SERVICE_NAME="${SERVICE_NAME:-capitalvoyage.service}"
BRANCH="${BRANCH:-main}"
VENV_PIP="$ROOT_DIR/.venv/bin/pip"

log() { printf '\033[1;34m[CapitalVoyage Update]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[CapitalVoyage Update]\033[0m %s\n' "$*" >&2; exit 1; }
run_as_deploy() { runuser -u "$DEPLOY_USER" -- "$@"; }

[[ "${EUID}" -eq 0 ]] || fail "请使用 root 账户运行；该账户负责重启 ${SERVICE_NAME}。"
[[ -d "$ROOT_DIR/.git" ]] || fail "未找到 Git 仓库：$ROOT_DIR"
[[ -x "$VENV_PIP" ]] || fail "未找到虚拟环境 pip：$VENV_PIP"

cd "$ROOT_DIR"
if [[ -n "$(run_as_deploy git status --porcelain --untracked-files=no)" ]]; then
  fail "服务器工作树存在已跟踪文件改动；请先处理后再更新。"
fi

before_commit="$(run_as_deploy git rev-parse HEAD)"
log "检查 origin/${BRANCH}…"
run_as_deploy git fetch origin "$BRANCH"
target_commit="$(run_as_deploy git rev-parse "origin/${BRANCH}")"

if [[ "$before_commit" == "$target_commit" ]]; then
  log "已经是最新版本：${before_commit:0:7}"
  exit 0
fi

log "更新 ${before_commit:0:7} → ${target_commit:0:7}…"
run_as_deploy git merge --ff-only "origin/${BRANCH}"
changed_files="$(run_as_deploy git diff --name-only "$before_commit" "$target_commit")"

if grep -qx 'backend/pyproject.toml' <<<"$changed_files"; then
  log "后端依赖定义已变化，正在更新依赖…"
  run_as_deploy "$VENV_PIP" install --disable-pip-version-check -e "$ROOT_DIR/backend"
fi

if grep -Eq '^frontend/(package\.json|package-lock\.json)$' <<<"$changed_files"; then
  log "前端依赖定义已变化，正在安装依赖…"
  run_as_deploy sh -lc "cd '$ROOT_DIR/frontend' && npm ci"
fi

log "构建前端生产资源…"
run_as_deploy sh -lc "cd '$ROOT_DIR/frontend' && npm run build"

if [[ "${RUN_TESTS:-0}" == "1" ]]; then
  log "运行后端测试…"
  run_as_deploy sh -lc "cd '$ROOT_DIR' && APP_ENV=test SCHEDULER_ENABLED=false '$ROOT_DIR/.venv/bin/python' -m pytest backend/tests"
fi

log "重启 ${SERVICE_NAME}…"
systemctl restart "$SERVICE_NAME"

for _ in {1..15}; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
    log "更新完成：${target_commit:0:7}，API 健康检查通过。"
    exit 0
  fi
  sleep 1
done

systemctl status "$SERVICE_NAME" --no-pager -l || true
fail "服务在 15 秒内未通过健康检查；请查看 journalctl -u ${SERVICE_NAME} -n 100。"
