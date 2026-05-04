#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${RUNTIME_DIR:-${ROOT_DIR}/runtime}"
PID_FILE="${RUNTIME_DIR}/gpu_idle_notifier.pid"

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null || true

    for _ in {1..10}; do
      if ! kill -0 "${PID}" 2>/dev/null; then
        break
      fi
      sleep 1
    done

    if kill -0 "${PID}" 2>/dev/null; then
      kill -9 "${PID}" 2>/dev/null || true
    fi

    echo "gpu_idle_notifier stopped (pid=${PID})"
  fi
fi

pkill -f "python -m gpu_idle_notifier" 2>/dev/null || true
rm -f "${PID_FILE}"

echo "gpu_idle_notifier is stopped"

