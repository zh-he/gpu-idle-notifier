from __future__ import annotations

import logging
import signal
import subprocess
import time

from .config import AppConfig, NotifyProviderConfig
from .gpu_query import NvidiaQueryClient
from .job_runner import JobRunner
from .message_builder import (
    build_gpu_status_message,
    build_job_finish_message,
    build_job_start_message,
)
from .models import GPUInfo
from .notifier import build_notifier
from .state_store import JsonStateStore


class GPUWatcher:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_store = JsonStateStore(config.state_file)
        self.state = self.state_store.load()
        self.query_client = NvidiaQueryClient(config.watch_gpu_indices, config.threshold)
        notify_providers = config.notify_providers
        if not notify_providers and config.send_key:
            # AppConfig objects built directly in tests may bypass load_config().
            notify_providers = [NotifyProviderConfig(type="serverchan", send_key=config.send_key)]
        self.notifier = build_notifier(notify_providers)
        self.job_runner = JobRunner(config.auto_run_job)
        self.running = True

    def stop(self, *_args: object) -> None:
        logging.info("Stop signal received. Exit watcher loop.")
        self.running = False

    def run(self) -> None:
        self._register_signal_handlers()
        logging.info("Watcher started | server=%s", self.config.server_name)

        while self.running:
            try:
                self.run_once()
            except subprocess.TimeoutExpired:
                logging.exception("nvidia-smi command timed out.")
            except subprocess.CalledProcessError as exc:
                logging.exception("nvidia-smi command failed: %s", exc)
            except Exception:
                logging.exception("Unexpected error in watcher loop.")

            if self.running:
                time.sleep(self.config.check_interval)

    def run_once(self) -> None:
        gpus = self.query_client.fetch_gpus()
        confirmed_idle = self._update_idle_hits(gpus)

        summary = ", ".join(
            f"GPU{gpu.idx}:{'idle' if gpu.is_idle else 'busy'}" for gpu in gpus
        ) or "no-gpu"
        logging.info("Check completed | %s", summary)

        idle_notified = self._maybe_notify(gpus, confirmed_idle)
        job_ran = self._maybe_run_auto_job(gpus, confirmed_idle)
        if self._should_stop_after_once_work(idle_notified, job_ran):
            self.running = False
        self.state_store.save(self.state)

    def _register_signal_handlers(self) -> None:
        for name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, name, None)
            if sig is not None:
                signal.signal(sig, self.stop)

    def _update_idle_hits(self, gpus: list[GPUInfo]) -> list[GPUInfo]:
        confirmed_idle: list[GPUInfo] = []

        current_indices = {str(gpu.idx) for gpu in gpus}
        for idx in list(self.state.idle_hits.keys()):
            if idx not in current_indices:
                self.state.idle_hits.pop(idx, None)

        for gpu in gpus:
            key = str(gpu.idx)
            if gpu.is_idle:
                self.state.idle_hits[key] = self.state.idle_hits.get(key, 0) + 1
            else:
                self.state.idle_hits[key] = 0

            if self.state.idle_hits[key] >= self.config.idle_consecutive_hits:
                confirmed_idle.append(gpu)

        return confirmed_idle

    def _maybe_notify(self, gpus: list[GPUInfo], confirmed_idle: list[GPUInfo]) -> bool:
        now = time.time()
        idle_indices = sorted(gpu.idx for gpu in confirmed_idle)
        last_idle_indices = sorted(self.state.last_notified_idle_set)
        idle_notified = False

        if len(idle_indices) >= self.config.min_idle_gpus:
            state_changed = idle_indices != last_idle_indices
            cooldown_ok = (now - self.state.last_notify_time) >= self.config.cooldown_seconds

            if state_changed or cooldown_ok:
                title, body = build_gpu_status_message(
                    server_name=self.config.server_name,
                    title_prefix="GPU Idle Alert",
                    all_gpus=gpus,
                    target_gpus=confirmed_idle,
                )
                if self.notifier.send_markdown(title, body):
                    self.state.last_notified_idle_set = idle_indices
                    self.state.last_notify_time = now
                    idle_notified = True

        if self.config.recover_notify:
            recovered_indices = sorted(set(last_idle_indices) - set(idle_indices))
            if recovered_indices:
                recovered_gpus = [gpu for gpu in gpus if gpu.idx in recovered_indices]
                title, body = build_gpu_status_message(
                    server_name=self.config.server_name,
                    title_prefix="GPU Recovered",
                    all_gpus=gpus,
                    target_gpus=recovered_gpus,
                    target_status="RECOVERED",
                )
                if self.notifier.send_markdown(title, body):
                    self.state.last_notified_recover_set = recovered_indices
                    # Move the baseline to current idle set so recovered alert is not repeated.
                    self.state.last_notified_idle_set = idle_indices
                    self.state.last_notify_time = now

        return idle_notified

    def _maybe_run_auto_job(self, all_gpus: list[GPUInfo], confirmed_idle: list[GPUInfo]) -> bool:
        job_cfg = self.config.auto_run_job
        if not job_cfg.enabled:
            return False

        idle_indices = sorted(gpu.idx for gpu in confirmed_idle)
        required_idle = max(self.config.min_idle_gpus, job_cfg.min_idle_gpus)
        if len(idle_indices) < required_idle:
            if self.state.last_job_idle_set:
                # Reset the idle cycle once GPUs become busy or insufficient.
                self.state.last_job_idle_set = []
            return False

        now = time.time()
        same_idle_set = idle_indices == sorted(self.state.last_job_idle_set)
        cooldown_ok = (now - self.state.last_job_run_time) >= job_cfg.cooldown_seconds

        # Only daemon mode needs a same-idle-set guard; once mode exits after one job.
        if self.config.mode == "daemon":
            if job_cfg.run_once_per_idle:
                if same_idle_set:
                    return False
            elif same_idle_set and not cooldown_ok:
                return False

        logging.info("Auto job triggered on idle GPUs: %s", idle_indices)

        if job_cfg.notify_on_start:
            title, body = build_job_start_message(
                server_name=self.config.server_name,
                command=job_cfg.command,
                all_gpus=all_gpus,
                idle_indices=idle_indices,
            )
            self.notifier.send_markdown(title, body)

        result = self.job_runner.run(idle_indices)

        if job_cfg.notify_on_finish:
            title, body = build_job_finish_message(
                server_name=self.config.server_name,
                all_gpus=all_gpus,
                idle_indices=idle_indices,
                result=result,
            )
            self.notifier.send_markdown(title, body)

        self.state.last_job_idle_set = idle_indices
        self.state.last_job_run_time = time.time()
        return True

    def _should_stop_after_once_work(self, idle_notified: bool, job_ran: bool) -> bool:
        # Personal queueing should finish cleanly instead of staying as a monitor.
        if self.config.mode != "once":
            return False

        if job_ran:
            logging.info("Once mode job finished. Exit watcher loop.")
            return True

        if not self.config.auto_run_job.enabled and idle_notified:
            logging.info("Once mode idle notification sent. Exit watcher loop.")
            return True

        return False
