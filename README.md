# GPU Idle Notifier

[中文README](./README.zh.md)

Monitor NVIDIA GPUs on shared servers. When GPUs are idle, send notifications, optionally start a job, and send another notification when the job finishes.

## Features

- Monitor GPU utilization, memory usage, and compute processes with `nvidia-smi`
- Confirm idle state after multiple consecutive checks
- Send idle, recovery, job-start, and job-finish notifications
- Support ServerChan, Feishu custom bot, and generic webhook
- Run a Python script, shell script, or command sequence after GPUs become idle
- Set `CUDA_VISIBLE_DEVICES` automatically for the started job
- Support personal one-shot mode and admin daemon mode
- Keep one watcher instance through a lock file
- Write each job to an independent log file

## Modes

| Mode | Use Case | Behavior |
|---|---|---|
| `once` | Personal job queue | Notify, run the configured job, send finish notification, then exit |
| `daemon` | Admin monitoring | Keep monitoring and sending notifications until stopped |

For admins, use `daemon` with Feishu and keep `job.enabled` as `false`.

## Minimal Config

Copy the example config:

```bash
cp config.example.json config.json
```

Example:

```json
{
  "mode": "once",
  "server_name": "A100-Lab",
  "check_interval_minutes": 20,
  "idle_consecutive_hits": 3,
  "cooldown_minutes": 30,
  "notify": {
    "providers": [
      {
        "type": "feishu",
        "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
      }
    ]
  },
  "job": {
    "enabled": true,
    "command": "bash run.sh",
    "working_dir": ".",
    "gpus": [0],
    "notify_on_start": true,
    "notify_on_finish": true
  }
}
```

Admin notification-only config:

```json
{
  "mode": "daemon",
  "server_name": "A100-Lab",
  "check_interval_minutes": 20,
  "idle_consecutive_hits": 3,
  "cooldown_minutes": 30,
  "notify": {
    "providers": [
      {
        "type": "feishu",
        "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
      }
    ]
  },
  "job": {
    "enabled": false
  }
}
```

## Start And Stop

Install dependencies:

```bash
pip install -r requirements.txt
```

Start on server:

```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

Check status:

```bash
./scripts/status.sh
```

Watch logs:

```bash
tail -f runtime/gpu_idle_notifier.out
```

Stop:

```bash
./scripts/stop.sh
```

## Main Fields

| Field | Description |
|---|---|
| `mode` | `once` or `daemon`; default `once` |
| `check_interval_minutes` | GPU polling interval; default `20` |
| `idle_consecutive_hits` | Consecutive idle checks required; default `3` |
| `cooldown_minutes` | Notification cooldown; default `30` |
| `threshold.util` | Max GPU utilization for idle; default `10` |
| `threshold.mem_mb` | Max memory usage for idle; default `2000` |
| `threshold.no_proc` | Require zero compute processes; default `true` |
| `notify.providers` | Notification channels: `serverchan`, `feishu`, `webhook` |
| `job.enabled` | Whether to run a job after GPUs become idle |
| `job.command` | Command, Python script, shell script, or command sequence |
| `job.gpus` | GPU indices to monitor and expose to the job |
| `job.working_dir` | Job working directory |
| `job.cooldown_minutes` | Job cooldown in daemon mode |
| `job.log_dir` | Per-job log directory; default `./runtime/jobs` |

Legacy fields such as `send_key`, `check_interval`, `cooldown_seconds`, `watch_gpu_indices`, and `auto_run_job` are still supported.
