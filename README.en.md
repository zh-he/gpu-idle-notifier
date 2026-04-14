# GPU Idle Notifier

A lightweight GPU idle monitoring tool for shared servers.

## Overview

`GPU Idle Notifier` periodically reads `nvidia-smi` metrics, sends ServerChan notifications when GPUs become idle, and can optionally run a user-defined job automatically.

## Features

- Periodic checks for GPU utilization, memory usage, and process count
- Consecutive-hit idle confirmation to reduce false positives
- Idle and recovery notifications
- Cooldown control to avoid notification spam
- Optional auto job execution when idle GPUs are available
- Job start and finish notifications (with return code and duration)
- Optional `CUDA_VISIBLE_DEVICES` injection for idle GPUs
- Persistent local state
- Single-instance lock protection

## Project Structure

```text
gpu-idle-notifier/
├── gpu_idle_notifier/
│   ├── __main__.py
│   ├── config.py
│   ├── gpu_query.py
│   ├── job_runner.py
│   ├── lock.py
│   ├── logging_utils.py
│   ├── message_builder.py
│   ├── models.py
│   ├── notifier.py
│   ├── state_store.py
│   └── watcher.py
├── config.example.json
├── config.json
├── gpu_idle_notifier.py
├── pyproject.toml
├── README.md
├── README.en.md
├── requirements.txt
└── examples/
    └── gpu-idle-notifier.service
```

## Installation

```bash
pip install -r requirements.txt
```

Optional editable install:

```bash
pip install -e .
```

## Quick Start

1. Copy config:

```bash
cp config.example.json config.json
```

2. Update at least:

- `send_key`
- `server_name`
- `auto_run_job.command`

3. Start service:

```bash
python -m gpu_idle_notifier --config ./config.json
```

Script entrypoint is also available:

```bash
python gpu_idle_notifier.py --config ./config.json
```

## Auto Job Example

```json
{
  "auto_run_job": {
    "enabled": true,
    "command": ["python", "train.py", "--epochs", "10"],
    "working_dir": ".",
    "min_idle_gpus": 1,
    "cooldown_seconds": 600,
    "timeout_seconds": 0,
    "set_cuda_visible_devices": true,
    "notify_on_start": true,
    "notify_on_finish": true,
    "extra_env": {
      "PYTHONUNBUFFERED": "1"
    }
  }
}
```

## Key Configuration Fields

| Field | Description |
|---|---|
| `check_interval` | Polling interval in seconds |
| `idle_consecutive_hits` | Consecutive checks required before confirming idle |
| `threshold.util` | Max GPU utilization (%) for idle |
| `threshold.mem_mb` | Max memory usage (MB) for idle |
| `threshold.no_proc` | Require zero compute processes |
| `min_idle_gpus` | Minimum idle GPUs for idle notifications |
| `cooldown_seconds` | Notification cooldown in seconds |
| `watch_gpu_indices` | Monitor only specific GPU indices |
| `auto_run_job.enabled` | Enable auto job trigger |
| `auto_run_job.command` | Job command to execute |
| `auto_run_job.notify_on_start` | Notify when job starts |
| `auto_run_job.notify_on_finish` | Notify when job completes |
| `auto_run_job.set_cuda_visible_devices` | Export idle GPUs to `CUDA_VISIBLE_DEVICES` |

## systemd

See `examples/gpu-idle-notifier.service`.
