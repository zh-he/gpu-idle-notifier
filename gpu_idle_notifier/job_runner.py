from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass

from .config import AutoRunJobConfig

_LOG_OUTPUT_TAIL = 500


@dataclass(slots=True)
class JobRunResult:
    ok: bool
    return_code: int
    duration_seconds: float
    error: str | None = None


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

        start_time = time.time()
        try:
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

            return JobRunResult(ok=ok, return_code=completed.returncode, duration_seconds=duration)
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            message = f"job timeout after {self.config.timeout_seconds} seconds"
            logging.exception("%s", message)
            return JobRunResult(ok=False, return_code=-1, duration_seconds=duration, error=message)
        except Exception as exc:
            duration = time.time() - start_time
            logging.exception("Failed to run auto job")
            return JobRunResult(ok=False, return_code=-1, duration_seconds=duration, error=str(exc))

    @staticmethod
    def _log_job_output(stdout: str, stderr: str) -> None:
        cleaned_stdout = stdout.strip()
        cleaned_stderr = stderr.strip()

        if cleaned_stdout:
            logging.info("Job stdout (tail): %s", cleaned_stdout[-_LOG_OUTPUT_TAIL:])
        if cleaned_stderr:
            logging.info("Job stderr (tail): %s", cleaned_stderr[-_LOG_OUTPUT_TAIL:])
