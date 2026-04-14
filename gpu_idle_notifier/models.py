from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GPUInfo:
    idx: int
    name: str
    util: int
    mem_used: int
    mem_total: int
    uuid: str
    proc_count: int
    users: list[str]
    is_idle: bool
