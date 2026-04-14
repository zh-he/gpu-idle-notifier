from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

DEFAULT_CONFIG_ENV = "GPU_IDLE_NOTIFIER_CONFIG"


@dataclass(slots=True)
class ThresholdConfig:
    util: int = 10
    mem_mb: int = 2000
    no_proc: bool = True

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ThresholdConfig":
        raw = raw or {}
        return cls(
            util=int(_pick(raw, "util", "UTIL", default=10)),
            mem_mb=int(_pick(raw, "mem_mb", "MEM_MB", default=2000)),
            no_proc=bool(_pick(raw, "no_proc", "NO_PROC", default=True)),
        )


@dataclass(slots=True)
class AutoRunJobConfig:
    enabled: bool = False
    command: list[str] = field(default_factory=list)
    working_dir: Path | None = None
    min_idle_gpus: int = 1
    cooldown_seconds: int = 0
    timeout_seconds: int = 0
    set_cuda_visible_devices: bool = True
    notify_on_start: bool = True
    notify_on_finish: bool = True
    extra_env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "AutoRunJobConfig":
        raw = raw or {}
        working_dir_raw = _pick(raw, "working_dir", "WORKING_DIR", default=None)
        working_dir = Path(str(working_dir_raw)) if working_dir_raw else None

        return cls(
            enabled=bool(_pick(raw, "enabled", "ENABLED", default=False)),
            command=_parse_command(_pick(raw, "command", "COMMAND", default=[])),
            working_dir=working_dir,
            min_idle_gpus=int(_pick(raw, "min_idle_gpus", "MIN_IDLE_GPUS", default=1)),
            cooldown_seconds=int(_pick(raw, "cooldown_seconds", "COOLDOWN_SECONDS", default=0)),
            timeout_seconds=int(_pick(raw, "timeout_seconds", "TIMEOUT_SECONDS", default=0)),
            set_cuda_visible_devices=bool(
                _pick(raw, "set_cuda_visible_devices", "SET_CUDA_VISIBLE_DEVICES", default=True)
            ),
            notify_on_start=bool(_pick(raw, "notify_on_start", "NOTIFY_ON_START", default=True)),
            notify_on_finish=bool(_pick(raw, "notify_on_finish", "NOTIFY_ON_FINISH", default=True)),
            extra_env=_parse_env(_pick(raw, "extra_env", "EXTRA_ENV", default={})),
        )

    def resolve_paths(self, base_dir: Path) -> "AutoRunJobConfig":
        if self.working_dir is None:
            return self
        return replace(self, working_dir=_resolve_path(self.working_dir, base_dir))

    def validate(self) -> None:
        if self.enabled and not self.command:
            raise ValueError("auto_run_job.command must be configured when auto_run_job.enabled is true")
        if self.min_idle_gpus <= 0:
            raise ValueError("auto_run_job.min_idle_gpus must be > 0")
        if self.cooldown_seconds < 0:
            raise ValueError("auto_run_job.cooldown_seconds must be >= 0")
        if self.timeout_seconds < 0:
            raise ValueError("auto_run_job.timeout_seconds must be >= 0")


@dataclass(slots=True)
class AppConfig:
    send_key: str = "your_serverchan_sendkey"
    server_name: str = "Lab-Server-01"
    check_interval: int = 300
    idle_consecutive_hits: int = 2
    recover_notify: bool = True
    cooldown_seconds: int = 1800
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    watch_gpu_indices: list[int] = field(default_factory=list)
    min_idle_gpus: int = 1
    state_file: Path = Path("./gpu_idle_notifier_state.json")
    lock_file: Path = Path("./gpu_idle_notifier.lock")
    log_file: Path = Path("./gpu_idle_notifier.log")
    auto_run_job: AutoRunJobConfig = field(default_factory=AutoRunJobConfig)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "AppConfig":
        raw = raw or {}
        return cls(
            send_key=str(_pick(raw, "send_key", "SENDKEY", default="your_serverchan_sendkey")),
            server_name=str(_pick(raw, "server_name", "SERVER_NAME", default="Lab-Server-01")),
            check_interval=int(_pick(raw, "check_interval", "CHECK_INTERVAL", default=300)),
            idle_consecutive_hits=int(
                _pick(raw, "idle_consecutive_hits", "IDLE_CONSECUTIVE_HITS", default=2)
            ),
            recover_notify=bool(_pick(raw, "recover_notify", "RECOVER_NOTIFY", default=True)),
            cooldown_seconds=int(_pick(raw, "cooldown_seconds", "COOLDOWN_SECONDS", default=1800)),
            threshold=ThresholdConfig.from_mapping(_pick(raw, "threshold", "THRESHOLD", default={})),
            watch_gpu_indices=_parse_gpu_indices(
                _pick(raw, "watch_gpu_indices", "WATCH_GPU_INDICES", default=[])
            ),
            min_idle_gpus=int(_pick(raw, "min_idle_gpus", "MIN_IDLE_GPUS", default=1)),
            state_file=Path(
                str(_pick(raw, "state_file", "STATE_FILE", default="./gpu_idle_notifier_state.json"))
            ),
            lock_file=Path(
                str(_pick(raw, "lock_file", "LOCK_FILE", default="./gpu_idle_notifier.lock"))
            ),
            log_file=Path(
                str(_pick(raw, "log_file", "LOG_FILE", default="./gpu_idle_notifier.log"))
            ),
            auto_run_job=AutoRunJobConfig.from_mapping(
                _pick(raw, "auto_run_job", "AUTO_RUN_JOB", default={})
            ),
        )

    def resolve_paths(self, base_dir: Path) -> "AppConfig":
        return replace(
            self,
            state_file=_resolve_path(self.state_file, base_dir),
            lock_file=_resolve_path(self.lock_file, base_dir),
            log_file=_resolve_path(self.log_file, base_dir),
            auto_run_job=self.auto_run_job.resolve_paths(base_dir),
        )

    def validate(self) -> None:
        if self.check_interval <= 0:
            raise ValueError("check_interval must be > 0")
        if self.idle_consecutive_hits <= 0:
            raise ValueError("idle_consecutive_hits must be > 0")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be >= 0")
        if self.min_idle_gpus <= 0:
            raise ValueError("min_idle_gpus must be > 0")
        if self.threshold.util < 0:
            raise ValueError("threshold.util must be >= 0")
        if self.threshold.mem_mb < 0:
            raise ValueError("threshold.mem_mb must be >= 0")

        self.auto_run_job.validate()


def load_config(config_path: str | Path | None = None) -> AppConfig:
    resolved_config_path: Path | None
    if config_path:
        resolved_config_path = Path(config_path).expanduser().resolve()
    else:
        env_path = os.getenv(DEFAULT_CONFIG_ENV, "").strip()
        resolved_config_path = Path(env_path).expanduser().resolve() if env_path else None

    config_raw: Mapping[str, Any] = {}
    if resolved_config_path:
        config_raw = _load_mapping_from_json(resolved_config_path)
        base_dir = resolved_config_path.parent
    else:
        base_dir = Path.cwd()

    config = AppConfig.from_mapping(config_raw).resolve_paths(base_dir)
    config.validate()
    return config


def _load_mapping_from_json(config_path: Path) -> Mapping[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    loaded = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise ValueError("Config must be a JSON object")
    return loaded


def _resolve_path(path: Path, base_dir: Path) -> Path:
    return path if path.is_absolute() else (base_dir / path).resolve()


def _pick(raw: Mapping[str, Any], *keys: str, default: Any) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return default


def _parse_gpu_indices(raw: Any) -> list[int]:
    if raw is None:
        return []

    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
        return [int(item) for item in values]

    if isinstance(raw, (list, tuple, set)):
        return [int(item) for item in raw]

    raise ValueError("watch_gpu_indices must be a list, tuple, set, or comma-separated string")


def _parse_command(raw: Any) -> list[str]:
    if raw is None:
        return []

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        return shlex.split(text, posix=os.name != "nt")

    if isinstance(raw, (list, tuple)):
        command = [str(item) for item in raw]
        return [item for item in command if item.strip()]

    raise ValueError("auto_run_job.command must be a string or list of string")


def _parse_env(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}

    if not isinstance(raw, Mapping):
        raise ValueError("auto_run_job.extra_env must be a mapping")

    return {str(key): str(value) for key, value in raw.items()}
