from __future__ import annotations

import csv
import logging
import os
import subprocess
from typing import Any

from .config import ThresholdConfig
from .models import GPUInfo


def run_command(command: list[str], timeout: int = 15) -> str:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout.strip()


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_get_username(pid: str) -> str:
    if os.name != "posix":
        return "unknown"

    try:
        import pwd

        stat_info = os.stat(f"/proc/{pid}")
        return pwd.getpwuid(stat_info.st_uid).pw_name
    except Exception:
        return "unknown"


class NvidiaQueryClient:
    def __init__(self, watch_gpu_indices: list[int], threshold: ThresholdConfig) -> None:
        self.watch_gpu_indices = set(watch_gpu_indices)
        self.threshold = threshold

    def fetch_gpus(self) -> list[GPUInfo]:
        raw_gpu_info = run_command(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,uuid",
                "--format=csv,noheader,nounits",
            ]
        )

        rows: list[dict[str, Any]] = []
        uuid_map: dict[str, dict[str, Any]] = {}
        for parsed in csv.reader(raw_gpu_info.splitlines(), skipinitialspace=True):
            if len(parsed) != 6:
                logging.warning("Skip malformed GPU row: %s", parsed)
                continue

            idx = _safe_int(parsed[0], default=-1)
            if idx < 0:
                continue
            if self.watch_gpu_indices and idx not in self.watch_gpu_indices:
                continue

            row = {
                "idx": idx,
                "name": parsed[1].strip(),
                "util": _safe_int(parsed[2]),
                "mem_used": _safe_int(parsed[3]),
                "mem_total": _safe_int(parsed[4]),
                "uuid": parsed[5].strip(),
                "proc_count": 0,
                "users": [],
            }
            rows.append(row)
            uuid_map[row["uuid"]] = row

        self._attach_process_info(uuid_map)

        gpus: list[GPUInfo] = []
        for row in rows:
            is_idle = self._is_idle(row["util"], row["mem_used"], row["proc_count"])
            gpus.append(
                GPUInfo(
                    idx=row["idx"],
                    name=row["name"],
                    util=row["util"],
                    mem_used=row["mem_used"],
                    mem_total=row["mem_total"],
                    uuid=row["uuid"],
                    proc_count=row["proc_count"],
                    users=row["users"],
                    is_idle=is_idle,
                )
            )
        return gpus

    def _attach_process_info(self, uuid_map: dict[str, dict[str, Any]]) -> None:
        try:
            raw_proc_info = run_command(
                [
                    "nvidia-smi",
                    "--query-compute-apps=gpu_uuid,pid,used_memory",
                    "--format=csv,noheader,nounits",
                ]
            )
        except subprocess.CalledProcessError:
            logging.info("No active GPU compute process.")
            return
        except Exception:
            logging.exception("Failed to query GPU process details.")
            return

        if not raw_proc_info.strip():
            return

        for parsed in csv.reader(raw_proc_info.splitlines(), skipinitialspace=True):
            if len(parsed) != 3:
                continue
            gpu_uuid = parsed[0].strip()
            pid = parsed[1].strip()
            used_memory = _safe_int(parsed[2])
            if gpu_uuid not in uuid_map:
                continue

            owner = _safe_get_username(pid)
            uuid_map[gpu_uuid]["proc_count"] += 1
            uuid_map[gpu_uuid]["users"].append(f"{owner}({used_memory}MB,pid={pid})")

    def _is_idle(self, util: int, mem_used: int, proc_count: int) -> bool:
        cond_util = util <= self.threshold.util
        cond_mem = mem_used <= self.threshold.mem_mb
        cond_proc = proc_count == 0 if self.threshold.no_proc else True
        return cond_util and cond_mem and cond_proc
