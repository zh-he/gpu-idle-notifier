#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${RUNTIME_DIR:-${ROOT_DIR}/runtime}"
PID_FILE="${RUNTIME_DIR}/gpu_idle_notifier.pid"
OUT_FILE="${RUNTIME_DIR}/gpu_idle_notifier.out"

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    echo "status: running"
    echo "pid: ${PID}"
    echo "log: ${OUT_FILE}"
    if [[ -f "${OUT_FILE}" ]]; then
      echo "---- last 20 log lines ----"
      tail -n 20 "${OUT_FILE}"
    fi
    exit 0
  fi
fi

echo "status: stopped"
exit 1

