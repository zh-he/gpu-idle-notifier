from __future__ import annotations

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from gpu_idle_notifier.config import AppConfig, AutoRunJobConfig
from gpu_idle_notifier.job_runner import JobRunResult
from gpu_idle_notifier.models import GPUInfo
from gpu_idle_notifier.watcher import GPUWatcher

WORKSPACE_TEMP_DIR = Path(__file__).resolve().parents[1] / ".tmp-tests"


class _FakeNotifier:
    def __init__(self) -> None:
        self.titles: list[str] = []

    def send_markdown(self, title: str, markdown_body: str) -> bool:
        self.titles.append(title)
        return True


class _FakeJobRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, idle_gpu_indices: list[int]) -> JobRunResult:
        self.calls += 1
        return JobRunResult(ok=True, return_code=0, duration_seconds=0.1)


class _FakeQueryClient:
    def __init__(self, gpus: list[GPUInfo]) -> None:
        self.gpus = gpus

    def fetch_gpus(self) -> list[GPUInfo]:
        return self.gpus


def _config_paths(prefix: str) -> dict[str, Path]:
    WORKSPACE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.time_ns()
    return {
        "state_file": WORKSPACE_TEMP_DIR / f"state-{prefix}-{ts}.json",
        "lock_file": WORKSPACE_TEMP_DIR / f"lock-{prefix}-{ts}.lock",
        "log_file": WORKSPACE_TEMP_DIR / f"log-{prefix}-{ts}.log",
    }


def _idle_gpu(idx: int) -> GPUInfo:
    return GPUInfo(
        idx=idx,
        name=f"GPU-{idx}",
        util=1,
        mem_used=100,
        mem_total=80000,
        uuid=f"uuid-{idx}",
        proc_count=0,
        users=[],
        is_idle=True,
    )


def _busy_gpu(idx: int) -> GPUInfo:
    return GPUInfo(
        idx=idx,
        name=f"GPU-{idx}",
        util=95,
        mem_used=70000,
        mem_total=80000,
        uuid=f"uuid-{idx}",
        proc_count=2,
        users=["tester(100MB,pid=1)"],
        is_idle=False,
    )


class WatcherNotifyTests(unittest.TestCase):
    def test_recovered_notification_sent_once_for_same_state(self) -> None:
        cfg = AppConfig(
            send_key="SCT-test",
            server_name="Test-Server",
            recover_notify=True,
            min_idle_gpus=1,
            cooldown_seconds=1800,
            **_config_paths("recover"),
        )

        watcher = GPUWatcher(cfg)
        fake_notifier = _FakeNotifier()
        watcher.notifier = fake_notifier

        watcher.state.last_notified_idle_set = [0]
        gpus = [_busy_gpu(0)]

        idle_notified, recovered_notified = watcher._maybe_notify(gpus, confirmed_idle=[])
        self.assertEqual(len(fake_notifier.titles), 1)
        self.assertIn("GPU Recovered", fake_notifier.titles[0])
        self.assertFalse(idle_notified)
        self.assertTrue(recovered_notified)

        watcher._maybe_notify(gpus, confirmed_idle=[])
        self.assertEqual(len(fake_notifier.titles), 1)

    def test_auto_job_runs_once_per_idle_cycle_by_default(self) -> None:
        cfg = AppConfig(
            mode="daemon",
            send_key="SCT-test",
            server_name="Test-Server",
            min_idle_gpus=1,
            auto_run_job=AutoRunJobConfig(
                enabled=True,
                command=["python", "job.py"],
                min_idle_gpus=1,
                cooldown_seconds=0,
                notify_on_start=False,
                notify_on_finish=False,
            ),
            **_config_paths("job"),
        )

        watcher = GPUWatcher(cfg)
        fake_runner = _FakeJobRunner()
        watcher.job_runner = fake_runner

        idle_gpus = [_idle_gpu(0)]
        watcher._maybe_run_auto_job(idle_gpus, idle_gpus)
        watcher._maybe_run_auto_job(idle_gpus, idle_gpus)
        self.assertEqual(fake_runner.calls, 1)

        watcher._maybe_run_auto_job([_busy_gpu(0)], [])
        watcher._maybe_run_auto_job(idle_gpus, idle_gpus)
        self.assertEqual(fake_runner.calls, 2)

    def test_once_mode_stops_after_auto_job_finishes(self) -> None:
        cfg = AppConfig(
            mode="once",
            send_key="SCT-test",
            server_name="Test-Server",
            idle_consecutive_hits=1,
            min_idle_gpus=1,
            auto_run_job=AutoRunJobConfig(
                enabled=True,
                command=["python", "job.py"],
                min_idle_gpus=1,
                notify_on_start=False,
                notify_on_finish=True,
            ),
            **_config_paths("once-job"),
        )

        watcher = GPUWatcher(cfg)
        fake_runner = _FakeJobRunner()
        watcher.query_client = _FakeQueryClient([_idle_gpu(0)])
        watcher.job_runner = fake_runner
        watcher.notifier = _FakeNotifier()

        watcher.run_once()

        self.assertEqual(fake_runner.calls, 1)
        self.assertFalse(watcher.running)

    def test_once_mode_runs_job_even_if_same_idle_set_was_saved(self) -> None:
        cfg = AppConfig(
            mode="once",
            send_key="SCT-test",
            server_name="Test-Server",
            min_idle_gpus=1,
            auto_run_job=AutoRunJobConfig(
                enabled=True,
                command=["python", "job.py"],
                min_idle_gpus=1,
                notify_on_start=False,
                notify_on_finish=False,
            ),
            **_config_paths("once-stale-state"),
        )

        watcher = GPUWatcher(cfg)
        fake_runner = _FakeJobRunner()
        watcher.job_runner = fake_runner
        watcher.state.last_job_idle_set = [0]

        idle_gpus = [_idle_gpu(0)]
        self.assertTrue(watcher._maybe_run_auto_job(idle_gpus, idle_gpus))
        self.assertEqual(fake_runner.calls, 1)

    def test_daemon_mode_keeps_running_after_auto_job_finishes(self) -> None:
        cfg = AppConfig(
            mode="daemon",
            send_key="SCT-test",
            server_name="Test-Server",
            idle_consecutive_hits=1,
            min_idle_gpus=1,
            auto_run_job=AutoRunJobConfig(
                enabled=True,
                command=["python", "job.py"],
                min_idle_gpus=1,
                notify_on_start=False,
                notify_on_finish=False,
            ),
            **_config_paths("daemon-job"),
        )

        watcher = GPUWatcher(cfg)
        fake_runner = _FakeJobRunner()
        watcher.query_client = _FakeQueryClient([_idle_gpu(0)])
        watcher.job_runner = fake_runner
        watcher.notifier = _FakeNotifier()

        watcher.run_once()

        self.assertEqual(fake_runner.calls, 1)
        self.assertTrue(watcher.running)

    def test_idle_notifications_use_exponential_backoff_and_max_count(self) -> None:
        cfg = AppConfig(
            mode="daemon",
            send_key="SCT-test",
            server_name="Test-Server",
            idle_consecutive_hits=1,
            idle_notify_max_count=3,
            min_idle_gpus=1,
            cooldown_seconds=10,
            **_config_paths("idle-backoff"),
        )

        watcher = GPUWatcher(cfg)
        fake_notifier = _FakeNotifier()
        watcher.notifier = fake_notifier
        idle_gpus = [_idle_gpu(0)]

        with patch("gpu_idle_notifier.watcher.time.time", side_effect=[100, 105, 110, 129, 130, 1000]):
            watcher._maybe_notify(idle_gpus, idle_gpus)
            watcher._maybe_notify(idle_gpus, idle_gpus)
            watcher._maybe_notify(idle_gpus, idle_gpus)
            watcher._maybe_notify(idle_gpus, idle_gpus)
            watcher._maybe_notify(idle_gpus, idle_gpus)
            watcher._maybe_notify(idle_gpus, idle_gpus)

        self.assertEqual(fake_notifier.titles.count("GPU Idle Alert Test-Server"), 3)
        self.assertEqual(watcher.state.idle_notify_count, 3)

    def test_once_mode_without_job_stops_after_idle_notification_limit(self) -> None:
        cfg = AppConfig(
            mode="once",
            send_key="SCT-test",
            server_name="Test-Server",
            idle_consecutive_hits=1,
            idle_notify_max_count=2,
            min_idle_gpus=1,
            cooldown_seconds=1,
            **_config_paths("once-notify"),
        )

        watcher = GPUWatcher(cfg)
        fake_notifier = _FakeNotifier()
        watcher.query_client = _FakeQueryClient([_idle_gpu(0)])
        watcher.notifier = fake_notifier

        with patch("gpu_idle_notifier.watcher.time.time", side_effect=[100, 101]):
            watcher.run_once()
            self.assertTrue(watcher.running)
            watcher.run_once()

        self.assertEqual(len(fake_notifier.titles), 2)
        self.assertFalse(watcher.running)

    def test_once_mode_without_job_stops_after_recovered_notification(self) -> None:
        cfg = AppConfig(
            mode="once",
            send_key="SCT-test",
            server_name="Test-Server",
            idle_consecutive_hits=1,
            idle_notify_max_count=3,
            min_idle_gpus=1,
            **_config_paths("once-recovered"),
        )

        watcher = GPUWatcher(cfg)
        fake_notifier = _FakeNotifier()
        watcher.query_client = _FakeQueryClient([_idle_gpu(0)])
        watcher.notifier = fake_notifier

        watcher.run_once()
        self.assertTrue(watcher.running)

        watcher.query_client = _FakeQueryClient([_busy_gpu(0)])
        watcher.run_once()

        self.assertEqual(len(fake_notifier.titles), 2)
        self.assertIn("GPU Idle Alert", fake_notifier.titles[0])
        self.assertIn("GPU Recovered", fake_notifier.titles[1])
        self.assertFalse(watcher.running)

    def test_daemon_mode_keeps_running_after_recovered_notification(self) -> None:
        cfg = AppConfig(
            mode="daemon",
            send_key="SCT-test",
            server_name="Test-Server",
            idle_consecutive_hits=1,
            min_idle_gpus=1,
            **_config_paths("daemon-recovered"),
        )

        watcher = GPUWatcher(cfg)
        watcher.query_client = _FakeQueryClient([_idle_gpu(0)])
        watcher.notifier = _FakeNotifier()

        watcher.run_once()
        watcher.query_client = _FakeQueryClient([_busy_gpu(0)])
        watcher.run_once()

        self.assertTrue(watcher.running)


if __name__ == "__main__":
    unittest.main()
