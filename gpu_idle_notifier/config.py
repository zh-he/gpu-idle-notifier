from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

DEFAULT_CONFIG_ENV = "GPU_IDLE_NOTIFIER_CONFIG"
DEFAULT_CHECK_INTERVAL_MINUTES = 20
DEFAULT_IDLE_CONSECUTIVE_HITS = 3
DEFAULT_NOTIFY_COOLDOWN_MINUTES = 30
SEND_KEY_ENV_CANDIDATES = (
    "GPU_IDLE_NOTIFIER_SEND_KEY",
    "SERVERCHAN_SEND_KEY",
    "SENDKEY",
    "SEND_KEY",
)
FEISHU_WEBHOOK_ENV_CANDIDATES = (
    "GPU_IDLE_NOTIFIER_FEISHU_WEBHOOK",
    "FEISHU_WEBHOOK",
)
SUPPORTED_NOTIFY_TYPES = {"serverchan", "feishu", "webhook"}
SUPPORTED_MODES = {"once", "daemon"}


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
            no_proc=_parse_bool(
                _pick(raw, "no_proc", "NO_PROC", default=True),
                "threshold.no_proc",
            ),
        )


@dataclass(slots=True)
class NotifyProviderConfig:
    type: str = "serverchan"
    send_key: str = ""
    webhook: str = ""
    name: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "NotifyProviderConfig":
        raw = raw or {}
        provider_type = str(
            _pick(raw, "type", "provider", "TYPE", "PROVIDER", default="serverchan")
        ).strip().lower()
        return cls(
            type=provider_type,
            send_key=str(_pick(raw, "send_key", "SENDKEY", "SEND_KEY", default="")).strip(),
            webhook=str(_pick(raw, "webhook", "url", "WEBHOOK", "URL", default="")).strip(),
            name=str(_pick(raw, "name", "NAME", default="")).strip(),
        )

    def validate(self) -> None:
        if self.type not in SUPPORTED_NOTIFY_TYPES:
            supported = ", ".join(sorted(SUPPORTED_NOTIFY_TYPES))
            raise ValueError(f"notify provider type must be one of: {supported}")


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
    run_once_per_idle: bool = True
    log_dir: Path | None = Path("./runtime/jobs")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "AutoRunJobConfig":
        raw = raw or {}
        working_dir_raw = _pick(raw, "working_dir", "WORKING_DIR", default=None)
        working_dir = Path(str(working_dir_raw)) if working_dir_raw else None

        return cls(
            enabled=_parse_bool(
                _pick(raw, "enabled", "ENABLED", default=False),
                "auto_run_job.enabled",
            ),
            command=_parse_command(_pick(raw, "command", "COMMAND", default=[])),
            working_dir=working_dir,
            min_idle_gpus=int(_pick(raw, "min_idle_gpus", "MIN_IDLE_GPUS", default=1)),
            cooldown_seconds=_parse_duration_seconds(
                raw,
                seconds_keys=("cooldown_seconds", "COOLDOWN_SECONDS"),
                minutes_keys=("cooldown_minutes", "COOLDOWN_MINUTES"),
                default_minutes=0,
            ),
            timeout_seconds=int(_pick(raw, "timeout_seconds", "TIMEOUT_SECONDS", default=0)),
            set_cuda_visible_devices=_parse_bool(
                _pick(raw, "set_cuda_visible_devices", "SET_CUDA_VISIBLE_DEVICES", default=True),
                "auto_run_job.set_cuda_visible_devices",
            ),
            notify_on_start=_parse_bool(
                _pick(raw, "notify_on_start", "NOTIFY_ON_START", default=True),
                "auto_run_job.notify_on_start",
            ),
            notify_on_finish=_parse_bool(
                _pick(raw, "notify_on_finish", "NOTIFY_ON_FINISH", default=True),
                "auto_run_job.notify_on_finish",
            ),
            extra_env=_parse_env(_pick(raw, "extra_env", "EXTRA_ENV", default={})),
            run_once_per_idle=_parse_bool(
                _pick(raw, "run_once_per_idle", "RUN_ONCE_PER_IDLE", default=True),
                "auto_run_job.run_once_per_idle",
            ),
            log_dir=_parse_optional_path(_pick(raw, "log_dir", "LOG_DIR", default="./runtime/jobs")),
        )

    def resolve_paths(self, base_dir: Path) -> "AutoRunJobConfig":
        working_dir = (
            _resolve_path(self.working_dir, base_dir) if self.working_dir is not None else None
        )
        log_dir = _resolve_path(self.log_dir, base_dir) if self.log_dir is not None else None
        return replace(self, working_dir=working_dir, log_dir=log_dir)

    def validate(self) -> None:
        if self.enabled and not self.command:
            raise ValueError("auto_run_job.command must be configured when auto_run_job.enabled is true")
        if self.min_idle_gpus <= 0:
            raise ValueError("auto_run_job.min_idle_gpus must be > 0")
        if self.cooldown_seconds < 0:
            raise ValueError("auto_run_job.cooldown_minutes/cooldown_seconds must be >= 0")
        if self.timeout_seconds < 0:
            raise ValueError("auto_run_job.timeout_seconds must be >= 0")


@dataclass(slots=True)
class AppConfig:
    mode: str = "once"
    send_key: str = ""
    server_name: str = "Lab-Server-01"
    check_interval: int = DEFAULT_CHECK_INTERVAL_MINUTES * 60
    idle_consecutive_hits: int = DEFAULT_IDLE_CONSECUTIVE_HITS
    recover_notify: bool = True
    cooldown_seconds: int = DEFAULT_NOTIFY_COOLDOWN_MINUTES * 60
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    watch_gpu_indices: list[int] = field(default_factory=list)
    min_idle_gpus: int = 1
    state_file: Path = Path("./gpu_idle_notifier_state.json")
    lock_file: Path = Path("./gpu_idle_notifier.lock")
    log_file: Path = Path("./gpu_idle_notifier.log")
    auto_run_job: AutoRunJobConfig = field(default_factory=AutoRunJobConfig)
    notify_providers: list[NotifyProviderConfig] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "AppConfig":
        raw = raw or {}
        # The short "job" block is mapped onto the older auto_run_job model so
        # existing deployments can keep their old config files unchanged.
        job_raw = _as_mapping(_pick(raw, "job", "JOB", default={}), "job")
        job_gpus = _parse_gpu_indices(_pick(job_raw, "gpus", "GPUS", default=[]))
        default_min_idle_gpus = len(job_gpus) if job_gpus else 1
        auto_run_job_raw = _build_auto_run_job_mapping(raw, job_raw, default_min_idle_gpus)

        return cls(
            mode=str(_pick(raw, "mode", "MODE", default="once")).strip().lower(),
            send_key=str(_pick(raw, "send_key", "SENDKEY", default="")),
            server_name=str(_pick(raw, "server_name", "SERVER_NAME", default="Lab-Server-01")),
            check_interval=_parse_check_interval_seconds(raw),
            idle_consecutive_hits=int(
                _pick(
                    raw,
                    "idle_consecutive_hits",
                    "IDLE_CONSECUTIVE_HITS",
                    default=DEFAULT_IDLE_CONSECUTIVE_HITS,
                )
            ),
            recover_notify=_parse_bool(
                _pick(raw, "recover_notify", "RECOVER_NOTIFY", default=True),
                "recover_notify",
            ),
            cooldown_seconds=_parse_duration_seconds(
                raw,
                seconds_keys=("cooldown_seconds", "COOLDOWN_SECONDS"),
                minutes_keys=("cooldown_minutes", "COOLDOWN_MINUTES"),
                default_minutes=DEFAULT_NOTIFY_COOLDOWN_MINUTES,
            ),
            threshold=ThresholdConfig.from_mapping(_pick(raw, "threshold", "THRESHOLD", default={})),
            watch_gpu_indices=_parse_gpu_indices(
                _pick(raw, "watch_gpu_indices", "WATCH_GPU_INDICES", default=job_gpus)
            ),
            min_idle_gpus=int(
                _pick(
                    raw,
                    "min_idle_gpus",
                    "MIN_IDLE_GPUS",
                    default=_pick(
                        job_raw,
                        "min_idle_gpus",
                        "MIN_IDLE_GPUS",
                        default=default_min_idle_gpus,
                    ),
                )
            ),
            state_file=Path(
                str(_pick(raw, "state_file", "STATE_FILE", default="./gpu_idle_notifier_state.json"))
            ),
            lock_file=Path(
                str(_pick(raw, "lock_file", "LOCK_FILE", default="./gpu_idle_notifier.lock"))
            ),
            log_file=Path(
                str(_pick(raw, "log_file", "LOG_FILE", default="./gpu_idle_notifier.log"))
            ),
            auto_run_job=AutoRunJobConfig.from_mapping(auto_run_job_raw),
            notify_providers=_parse_notify_providers(raw),
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
        if self.mode not in SUPPORTED_MODES:
            supported = ", ".join(sorted(SUPPORTED_MODES))
            raise ValueError(f"mode must be one of: {supported}")
        if self.check_interval <= 0:
            raise ValueError("check_interval_minutes/check_interval must be > 0")
        if self.idle_consecutive_hits <= 0:
            raise ValueError("idle_consecutive_hits must be > 0")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_minutes/cooldown_seconds must be >= 0")
        if self.min_idle_gpus <= 0:
            raise ValueError("min_idle_gpus must be > 0")
        if self.threshold.util < 0:
            raise ValueError("threshold.util must be >= 0")
        if self.threshold.mem_mb < 0:
            raise ValueError("threshold.mem_mb must be >= 0")

        self.auto_run_job.validate()
        for provider in self.notify_providers:
            provider.validate()


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
    send_key = _resolve_send_key(config.send_key)
    notify_providers = _resolve_notify_providers(config.notify_providers, send_key)
    config = replace(config, send_key=send_key, notify_providers=notify_providers)
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


def _resolve_send_key(config_value: str) -> str:
    for env_name in SEND_KEY_ENV_CANDIDATES:
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return env_value
    return (config_value or "").strip()


def _resolve_feishu_webhook() -> str:
    for env_name in FEISHU_WEBHOOK_ENV_CANDIDATES:
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return env_value
    return ""


def _resolve_notify_providers(
    providers: list[NotifyProviderConfig],
    fallback_send_key: str,
) -> list[NotifyProviderConfig]:
    feishu_webhook = _resolve_feishu_webhook()

    if not providers:
        # Legacy config only had send_key. Treat it as one ServerChan provider.
        resolved: list[NotifyProviderConfig] = []
        if fallback_send_key:
            resolved.append(NotifyProviderConfig(type="serverchan", send_key=fallback_send_key))
        if feishu_webhook:
            resolved.append(NotifyProviderConfig(type="feishu", webhook=feishu_webhook))
        return resolved

    resolved = []
    for provider in providers:
        if provider.type == "serverchan" and not provider.send_key:
            provider = replace(provider, send_key=fallback_send_key)
        elif provider.type == "feishu" and not provider.webhook:
            provider = replace(provider, webhook=feishu_webhook)
        resolved.append(provider)
    return resolved


def _parse_bool(raw: Any, field_name: str) -> bool:
    if isinstance(raw, bool):
        return raw

    if isinstance(raw, int):
        if raw in (0, 1):
            return bool(raw)
        raise ValueError(f"{field_name} must be a boolean (or 0/1)")

    if isinstance(raw, str):
        normalized = raw.strip().lower()
        truthy = {"1", "true", "yes", "y", "on"}
        falsy = {"0", "false", "no", "n", "off"}
        if normalized in truthy:
            return True
        if normalized in falsy:
            return False
        raise ValueError(f"{field_name} must be a boolean-like string")

    raise ValueError(f"{field_name} must be a boolean")


def _parse_check_interval_seconds(raw: Mapping[str, Any]) -> int:
    if "check_interval" in raw or "CHECK_INTERVAL" in raw:
        return int(_pick(raw, "check_interval", "CHECK_INTERVAL", default=0))

    minutes = float(
        _pick(
            raw,
            "check_interval_minutes",
            "CHECK_INTERVAL_MINUTES",
            default=DEFAULT_CHECK_INTERVAL_MINUTES,
        )
    )
    return int(minutes * 60)


def _parse_duration_seconds(
    raw: Mapping[str, Any],
    *,
    seconds_keys: tuple[str, ...],
    minutes_keys: tuple[str, ...],
    default_minutes: float,
) -> int:
    for key in seconds_keys:
        if key in raw:
            return int(raw[key])

    for key in minutes_keys:
        if key in raw:
            return int(float(raw[key]) * 60)

    return int(default_minutes * 60)


def _parse_gpu_indices(raw: Any) -> list[int]:
    if raw is None:
        return []

    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
        return [int(item) for item in values]

    if isinstance(raw, (list, tuple, set)):
        return [int(item) for item in raw]

    raise ValueError("watch_gpu_indices must be a list, tuple, set, or comma-separated string")


def _parse_optional_path(raw: Any) -> Path | None:
    if raw is None:
        return None

    value = str(raw).strip()
    return Path(value) if value else None


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


def _as_mapping(raw: Any, field_name: str) -> Mapping[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    return raw


def _parse_notify_providers(raw: Mapping[str, Any]) -> list[NotifyProviderConfig]:
    notify_raw = _pick(raw, "notify", "NOTIFY", default=None)
    if notify_raw is None:
        return []

    notify = _as_mapping(notify_raw, "notify")
    providers_raw = _pick(notify, "providers", "PROVIDERS", default=None)
    if providers_raw is None:
        return [NotifyProviderConfig.from_mapping(notify)] if notify else []

    if isinstance(providers_raw, Mapping):
        return [NotifyProviderConfig.from_mapping(providers_raw)]

    if isinstance(providers_raw, (list, tuple)):
        return [
            NotifyProviderConfig.from_mapping(_as_mapping(item, "notify.providers[]"))
            for item in providers_raw
        ]

    raise ValueError("notify.providers must be a list of provider objects")


def _build_auto_run_job_mapping(
    raw: Mapping[str, Any],
    job_raw: Mapping[str, Any],
    default_min_idle_gpus: int,
) -> Mapping[str, Any]:
    auto_run_job = dict(
        _as_mapping(
            _pick(raw, "auto_run_job", "AUTO_RUN_JOB", default={}),
            "auto_run_job",
        )
    )

    aliases = {
        "enabled": ("enabled", "ENABLED"),
        "command": ("command", "COMMAND"),
        "working_dir": ("working_dir", "WORKING_DIR"),
        "min_idle_gpus": ("min_idle_gpus", "MIN_IDLE_GPUS"),
        "cooldown_seconds": ("cooldown_seconds", "COOLDOWN_SECONDS"),
        "cooldown_minutes": ("cooldown_minutes", "COOLDOWN_MINUTES"),
        "timeout_seconds": ("timeout_seconds", "TIMEOUT_SECONDS"),
        "set_cuda_visible_devices": ("set_cuda_visible_devices", "SET_CUDA_VISIBLE_DEVICES"),
        "notify_on_start": ("notify_on_start", "NOTIFY_ON_START"),
        "notify_on_finish": ("notify_on_finish", "NOTIFY_ON_FINISH"),
        "extra_env": ("extra_env", "EXTRA_ENV"),
        "run_once_per_idle": ("run_once_per_idle", "RUN_ONCE_PER_IDLE"),
        "log_dir": ("log_dir", "LOG_DIR"),
    }

    for target_key, source_keys in aliases.items():
        for source_key in source_keys:
            if source_key in job_raw:
                auto_run_job[target_key] = job_raw[source_key]
                break

    # If users choose GPUs in the short config, require all of them by default.
    if (
        job_raw
        and "min_idle_gpus" not in auto_run_job
        and "MIN_IDLE_GPUS" not in auto_run_job
        and default_min_idle_gpus > 0
    ):
        auto_run_job["min_idle_gpus"] = default_min_idle_gpus

    return auto_run_job
