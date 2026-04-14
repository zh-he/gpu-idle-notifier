# GPU Idle Notifier

[English README](./README.en.md)

---

## 中文说明

### 项目简介

`GPU Idle Notifier` 是一个面向服务器场景的 GPU 空闲监控工具。它会周期性读取 `nvidia-smi` 数据，在 GPU 满足空闲条件时发送 ServerChan（微信）通知，并可自动触发你指定的任务脚本。

### 功能特性

- 周期检测 GPU 利用率、显存占用、计算进程
- 连续命中判定，降低误报
- 空闲通知与恢复通知
- 通知冷却时间控制
- 空闲时自动执行任务（如 `python train.py`）
- 自动任务开始和结束通知（含返回码、耗时）
- 自动注入 `CUDA_VISIBLE_DEVICES`
- 本地状态持久化
- 单实例锁保护

### 目录结构

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

### 安装

```bash
pip install -r requirements.txt
```

可选（开发模式安装）：

```bash
pip install -e .
```

### 快速开始

1. 复制配置文件：

```bash
cp config.example.json config.json
```

2. 修改 `config.json`，至少设置：

- `send_key`
- `server_name`
- `auto_run_job.command`

3. 启动监控：

```bash
python -m gpu_idle_notifier --config ./config.json
```

也可使用脚本入口：

```bash
python gpu_idle_notifier.py --config ./config.json
```

### 自动任务配置示例

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

### 核心配置项

| 字段 | 说明 |
|---|---|
| `check_interval` | 轮询间隔（秒） |
| `idle_consecutive_hits` | 连续命中次数，达到后判定空闲 |
| `threshold.util` | 空闲最大 GPU 利用率（%） |
| `threshold.mem_mb` | 空闲最大显存占用（MB） |
| `threshold.no_proc` | 是否要求无计算进程 |
| `min_idle_gpus` | 空闲通知的最少空闲 GPU 数 |
| `cooldown_seconds` | 通知冷却时间（秒） |
| `watch_gpu_indices` | 仅监控指定 GPU 序号 |
| `auto_run_job.enabled` | 是否启用自动任务 |
| `auto_run_job.command` | 自动执行命令 |
| `auto_run_job.notify_on_start` | 任务开始时通知 |
| `auto_run_job.notify_on_finish` | 任务结束时通知 |
| `auto_run_job.set_cuda_visible_devices` | 注入空闲卡到 `CUDA_VISIBLE_DEVICES` |

### systemd

示例文件：`examples/gpu-idle-notifier.service`

---

## English

For the complete English documentation, see [README.en.md](./README.en.md).
