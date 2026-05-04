from __future__ import annotations

import logging
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import AutoRunJobConfig

_LOG_OUTPUT_TAIL = 500


@dataclass(slots=True)
class JobRunResult:
    ok: bool
    return_code: int
    duration_seconds: float
    error: str | None = None
    log_file: str | None = None


class JobRunner:
    """Run user-defined jobs when idle GPU conditions are met."""

    def __init__(self, config: AutoRunJobConfig) -> None:
        self.config = config

    def run(self, idle_gpu_indices: list[int]) -> JobRunResult:
        env = os.environ.copy()
        env.update(self.config.extra_env)

        if self.config.set_cuda_visible_devices and idle_gpu_indices:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(idx) for idx in idle_gpu_indices)

        timeout = self.config.timeout_seconds if self.config.timeout_seconds > 0 else None
        cwd = str(self.config.working_dir) if self.config.working_dir else None
        log_path = self._build_log_path()

        start_time = time.time()
        try:
            if log_path:
                completed = self._run_with_log_file(cwd, env, timeout, log_path)
            else:
                completed = subprocess.run(
                    self.config.command,
                    cwd=cwd,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                )

            duration = time.time() - start_time
            if log_path:
                self._log_job_output_tail(log_path)
            else:
                self._log_job_output(completed.stdout, completed.stderr)

            ok = completed.returncode == 0
            if ok:
                logging.info("Auto job completed successfully, duration=%.1fs", duration)
            else:
                logging.warning(
                    "Auto job exited with non-zero return code=%s, duration=%.1fs",
                    completed.returncode,
                    duration,
                )

            return JobRunResult(
                ok=ok,
                return_code=completed.returncode,
                duration_seconds=duration,
                log_file=str(log_path) if log_path else None,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            message = f"job timeout after {self.config.timeout_seconds} seconds"
            logging.exception("%s", message)
            self._append_log_error(log_path, message)
            return JobRunResult(
                ok=False,
                return_code=-1,
                duration_seconds=duration,
                error=message,
                log_file=str(log_path) if log_path else None,
            )
        except Exception as exc:
            duration = time.time() - start_time
            logging.exception("Failed to run auto job")
            self._append_log_error(log_path, str(exc))
            return JobRunResult(
                ok=False,
                return_code=-1,
                duration_seconds=duration,
                error=str(exc),
                log_file=str(log_path) if log_path else None,
            )

    def _build_log_path(self) -> Path | None:
        if self.config.log_dir is None:
            return None

        # Keep long training output out of the watcher log and make failures easier to inspect.
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = int(time.time() * 1000) % 1000
        return self.config.log_dir / f"{timestamp}-{suffix:03d}.log"

    def _run_with_log_file(
        self,
        cwd: str | None,
        env: dict[str, str],
        timeout: int | None,
        log_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            log_file.write(f"command: {shlex.join(self.config.command)}\n")
            log_file.write(f"working_dir: {cwd or os.getcwd()}\n")
            if "CUDA_VISIBLE_DEVICES" in env:
                log_file.write(f"CUDA_VISIBLE_DEVICES: {env['CUDA_VISIBLE_DEVICES']}\n")
            log_file.write("\n")
            log_file.flush()

            return subprocess.run(
                self.config.command,
                cwd=cwd,
                env=env,
                text=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )

    @staticmethod
    def _log_job_output(stdout: str, stderr: str) -> None:
        cleaned_stdout = stdout.strip()
        cleaned_stderr = stderr.strip()

        if cleaned_stdout:
            logging.info("Job stdout (tail): %s", cleaned_stdout[-_LOG_OUTPUT_TAIL:])
        if cleaned_stderr:
            logging.info("Job stderr (tail): %s", cleaned_stderr[-_LOG_OUTPUT_TAIL:])

    @staticmethod
    def _log_job_output_tail(log_path: Path) -> None:
        try:
            with log_path.open("rb") as log_file:
                log_file.seek(0, os.SEEK_END)
                size = log_file.tell()
                log_file.seek(max(size - 4096, 0))
                tail = log_file.read().decode("utf-8", errors="replace").strip()
            if tail:
                logging.info("Job log: %s", log_path)
                logging.info("Job log tail: %s", tail[-_LOG_OUTPUT_TAIL:])
        except Exception:
            logging.exception("Failed to read job log tail: %s", log_path)

    @staticmethod
    def _append_log_error(log_path: Path | None, message: str) -> None:
        if log_path is None:
            return
        try:
            with log_path.open("a", encoding="utf-8", errors="replace") as log_file:
                log_file.write(f"\n[error] {message}\n")
        except Exception:
            logging.exception("Failed to append job error to log: %s", log_path)
