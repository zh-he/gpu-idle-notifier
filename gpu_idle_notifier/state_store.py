from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class WatcherState:
    last_notified_idle_set: list[int] = field(default_factory=list)
    last_notified_recover_set: list[int] = field(default_factory=list)
    last_notify_time: float = 0.0
    idle_hits: dict[str, int] = field(default_factory=dict)

    last_job_idle_set: list[int] = field(default_factory=list)
    last_job_run_time: float = 0.0

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "WatcherState":
        raw = raw or {}
        idle_hits = raw.get("idle_hits", {})
        if not isinstance(idle_hits, dict):
            idle_hits = {}

        return cls(
            last_notified_idle_set=[int(item) for item in raw.get("last_notified_idle_set", [])],
            last_notified_recover_set=[int(item) for item in raw.get("last_notified_recover_set", [])],
            last_notify_time=float(raw.get("last_notify_time", 0.0)),
            idle_hits={str(k): int(v) for k, v in idle_hits.items()},
            last_job_idle_set=[int(item) for item in raw.get("last_job_idle_set", [])],
            last_job_run_time=float(raw.get("last_job_run_time", 0.0)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "last_notified_idle_set": self.last_notified_idle_set,
            "last_notified_recover_set": self.last_notified_recover_set,
            "last_notify_time": self.last_notify_time,
            "idle_hits": self.idle_hits,
            "last_job_idle_set": self.last_job_idle_set,
            "last_job_run_time": self.last_job_run_time,
        }


class JsonStateStore:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path

    def load(self) -> WatcherState:
        if not self.state_path.exists():
            return WatcherState()

        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8-sig"))
            if not isinstance(loaded, dict):
                raise ValueError("State file is not a JSON object")
            return WatcherState.from_mapping(loaded)
        except Exception:
            logging.exception("Failed to read state file. Fallback to default state.")
            return WatcherState()

    def save(self, state: WatcherState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(state.to_mapping(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.state_path)
