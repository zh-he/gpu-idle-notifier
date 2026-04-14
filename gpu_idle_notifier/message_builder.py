from __future__ import annotations

import shlex
import time

from .job_runner import JobRunResult
from .models import GPUInfo


def build_gpu_status_message(
    *,
    server_name: str,
    title_prefix: str,
    all_gpus: list[GPUInfo],
    target_gpus: list[GPUInfo],
) -> tuple[str, str]:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    target_ids = ", ".join(f"GPU {gpu.idx}" for gpu in target_gpus) if target_gpus else "none"

    title = f"{title_prefix} {server_name}"
    lines = [
        f"### {title_prefix} {server_name}",
        "",
        f"**Check Time**: {now_str}",
        f"**Target GPUs**: {target_ids}",
        "",
        "| ID | Model | Util | Memory | Proc Count | Users | Status |",
        "|:--:|:--|:--:|:--|:--:|:--|:--:|",
    ]

    target_set = {gpu.idx for gpu in target_gpus}
    for gpu in all_gpus:
        users = ", ".join(gpu.users) if gpu.users else "-"
        if gpu.idx in target_set:
            status = "IDLE"
        elif gpu.is_idle:
            status = "CANDIDATE"
        else:
            status = "BUSY"

        lines.append(
            f"| {gpu.idx} | {gpu.name} | {gpu.util}% | "
            f"{gpu.mem_used}/{gpu.mem_total}MB | {gpu.proc_count} | {users} | {status} |"
        )

    return title, "\n".join(lines)


def build_job_start_message(
    *,
    server_name: str,
    command: list[str],
    all_gpus: list[GPUInfo],
    idle_indices: list[int],
) -> tuple[str, str]:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    title = f"Auto Job Started {server_name}"

    lines = [
        f"### Auto Job Started {server_name}",
        "",
        f"**Start Time**: {now_str}",
        f"**Idle GPUs**: {', '.join(map(str, idle_indices))}",
        f"**Command**: `{format_command(command)}`",
        "",
        "| ID | Model | Util | Memory | Proc Count | Status |",
        "|:--:|:--|:--:|:--|:--:|:--:|",
    ]

    idle_set = set(idle_indices)
    for gpu in all_gpus:
        status = "IDLE" if gpu.idx in idle_set else "OTHER"
        lines.append(
            f"| {gpu.idx} | {gpu.name} | {gpu.util}% | "
            f"{gpu.mem_used}/{gpu.mem_total}MB | {gpu.proc_count} | {status} |"
        )

    return title, "\n".join(lines)


def build_job_finish_message(
    *,
    server_name: str,
    all_gpus: list[GPUInfo],
    idle_indices: list[int],
    result: JobRunResult,
) -> tuple[str, str]:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if result.ok else "FAILED"
    title = f"Auto Job {status} {server_name}"

    lines = [
        f"### Auto Job {status} {server_name}",
        "",
        f"**Finish Time**: {now_str}",
        f"**Idle GPUs (trigger)**: {', '.join(map(str, idle_indices))}",
        f"**Return Code**: {result.return_code}",
        f"**Duration**: {result.duration_seconds:.1f}s",
    ]

    if result.error:
        lines.append(f"**Error**: {result.error}")

    lines += [
        "",
        "| ID | Model | Util | Memory | Proc Count | Status |",
        "|:--:|:--|:--:|:--|:--:|:--:|",
    ]

    idle_set = set(idle_indices)
    for gpu in all_gpus:
        label = "TRIGGER_IDLE" if gpu.idx in idle_set else "OTHER"
        lines.append(
            f"| {gpu.idx} | {gpu.name} | {gpu.util}% | "
            f"{gpu.mem_used}/{gpu.mem_total}MB | {gpu.proc_count} | {label} |"
        )

    return title, "\n".join(lines)


def format_command(command: list[str]) -> str:
    if not command:
        return ""
    return shlex.join(command)
