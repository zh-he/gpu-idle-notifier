#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

CONFIG_PATH="${CONFIG_PATH:-${ROOT_DIR}/config.json}"
RUNTIME_DIR="${RUNTIME_DIR:-${ROOT_DIR}/runtime}"
PID_FILE="${RUNTIME_DIR}/gpu_idle_notifier.pid"
OUT_FILE="${RUNTIME_DIR}/gpu_idle_notifier.out"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Config file not found: ${CONFIG_PATH}" >&2
  exit 1
fi

mkdir -p "${RUNTIME_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}")"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "gpu_idle_notifier is already running (pid=${OLD_PID})"
    exit 0
  fi
fi

cd "${ROOT_DIR}"
nohup "${PYTHON_BIN}" -m gpu_idle_notifier --config "${CONFIG_PATH}" >> "${OUT_FILE}" 2>&1 &
NEW_PID=$!
echo "${NEW_PID}" > "${PID_FILE}"

sleep 1
if kill -0 "${NEW_PID}" 2>/dev/null; then
  echo "gpu_idle_notifier started (pid=${NEW_PID})"
  echo "log: ${OUT_FILE}"
  exit 0
fi

echo "gpu_idle_notifier failed to start, check log: ${OUT_FILE}" >&2
exit 1

