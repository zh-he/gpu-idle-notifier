from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

from gpu_idle_notifier.config import AutoRunJobConfig
from gpu_idle_notifier.job_runner import JobRunner

WORKSPACE_TEMP_DIR = Path(__file__).resolve().parents[1] / ".tmp-tests"


class JobRunnerTests(unittest.TestCase):
    def test_job_output_is_written_to_log_file(self) -> None:
        WORKSPACE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        log_dir = WORKSPACE_TEMP_DIR / f"job-logs-{int(time.time() * 1000)}"
        cfg = AutoRunJobConfig(
            enabled=True,
            command=[sys.executable, "-c", "print('hello from job')"],
            log_dir=log_dir,
        )

        result = JobRunner(cfg).run([0])

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.log_file)
        log_file = Path(result.log_file or "")
        self.assertTrue(log_file.exists())
        self.assertIn("hello from job", log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
