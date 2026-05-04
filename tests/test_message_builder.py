from __future__ import annotations

import unittest

from gpu_idle_notifier.job_runner import JobRunResult
from gpu_idle_notifier.message_builder import (
    build_gpu_status_message,
    build_job_finish_message,
    build_job_start_message,
)
from gpu_idle_notifier.models import GPUInfo


def _gpu(idx: int, is_idle: bool) -> GPUInfo:
    return GPUInfo(
        idx=idx,
        name=f"GPU-{idx}",
        util=0 if is_idle else 90,
        mem_used=100,
        mem_total=20000,
        uuid=f"uuid-{idx}",
        proc_count=0 if is_idle else 2,
        users=[] if is_idle else ["user(100MB,pid=1)"],
        is_idle=is_idle,
    )


class MessageBuilderTests(unittest.TestCase):
    def test_build_gpu_status_message(self) -> None:
        gpus = [_gpu(0, True), _gpu(1, False)]
        title, body = build_gpu_status_message(
            server_name="Server-A",
            title_prefix="GPU Idle Alert",
            all_gpus=gpus,
            target_gpus=[gpus[0]],
        )

        self.assertIn("GPU Idle Alert Server-A", title)
        self.assertIn("GPU 0", body)
        self.assertIn("IDLE", body)
        self.assertIn("BUSY", body)

    def test_build_gpu_recovered_status_message(self) -> None:
        gpus = [_gpu(0, False)]
        title, body = build_gpu_status_message(
            server_name="Server-A",
            title_prefix="GPU Recovered",
            all_gpus=gpus,
            target_gpus=[gpus[0]],
            target_status="RECOVERED",
        )

        self.assertIn("GPU Recovered Server-A", title)
        self.assertIn("RECOVERED", body)
        self.assertNotIn("| IDLE |", body)

    def test_build_job_messages(self) -> None:
        gpus = [_gpu(0, True)]

        start_title, start_body = build_job_start_message(
            server_name="Server-A",
            command=["python", "train.py", "--epochs", "1"],
            all_gpus=gpus,
            idle_indices=[0],
        )
        self.assertIn("Auto Job Started Server-A", start_title)
        self.assertIn("python train.py --epochs 1", start_body)

        finish_title, finish_body = build_job_finish_message(
            server_name="Server-A",
            all_gpus=gpus,
            idle_indices=[0],
            result=JobRunResult(ok=True, return_code=0, duration_seconds=12.3),
        )
        self.assertIn("Auto Job SUCCESS Server-A", finish_title)
        self.assertIn("Return Code", finish_body)


if __name__ == "__main__":
    unittest.main()
