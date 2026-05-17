# GPU Idle Notifier

[English README](./README.md)

用于共享服务器的 NVIDIA GPU 空闲监控工具。GPU 空闲时发送通知，可选择自动启动任务，并在任务结束后再次通知。

## 功能

- 使用 `nvidia-smi` 监控 GPU 利用率、显存和计算进程
- 连续多次检测为空闲后才确认空闲状态
- 支持空闲通知、恢复通知、任务开始通知、任务结束通知
- 支持 ServerChan、飞书自定义机器人和通用 webhook
- GPU 空闲后可执行 Python 脚本、shell 脚本或命令序列
- 自动为任务设置 `CUDA_VISIBLE_DEVICES`
- 支持个人一次性模式和管理员常驻模式
- 使用锁文件避免重复启动多个监控实例
- 每次任务写入独立日志文件

## 运行模式

| 模式 | 使用场景 | 行为 |
|---|---|---|
| `once` | 个人等待一次机会 | 运行一次任务后退出；未配置任务时，达到通知上限或发送恢复通知后退出 |
| `daemon` | 管理员监控 | 持续监控并发送通知，直到手动停止 |

管理员建议使用 `daemon`，通知方式用飞书，并保持 `job.enabled` 为 `false`。

## 最小配置

克隆项目：

```bash
git clone https://github.com/zh-he/gpu-idle-notifier.git
cd gpu-idle-notifier
```

安装依赖：

```bash
pip install -r requirements.txt
```

复制配置模板：

```bash
cp config.example.json config.json
```

个人任务示例：

```json
{
  "mode": "once",
  "server_name": "A100-Lab",
  "check_interval_minutes": 20,
  "idle_consecutive_hits": 3,
  "idle_notify_max_count": 3,
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

管理员只通知示例：

```json
{
  "mode": "daemon",
  "server_name": "A100-Lab",
  "check_interval_minutes": 20,
  "idle_consecutive_hits": 3,
  "idle_notify_max_count": 3,
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

## 启动和停止

服务器启动：

```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

查看状态：

```bash
./scripts/status.sh
```

查看日志：

```bash
tail -f runtime/gpu_idle_notifier.out
```

停止：

```bash
./scripts/stop.sh
```

## 主要字段

| 字段 | 说明 |
|---|---|
| `mode` | `once` 或 `daemon`，默认 `once` |
| `check_interval_minutes` | GPU 检查间隔，默认 `20` 分钟 |
| `idle_consecutive_hits` | 连续空闲命中次数，默认 `3` |
| `idle_notify_max_count` | 同一轮空闲最多通知次数，默认 `3` |
| `cooldown_minutes` | 指数空闲通知的基础冷却时间，默认 `30` 分钟 |
| `threshold.util` | 判定空闲的最高 GPU 利用率，默认 `10` |
| `threshold.mem_mb` | 判定空闲的最高显存占用，默认 `2000` |
| `threshold.no_proc` | 是否要求没有计算进程，默认 `true` |
| `notify.providers` | 通知渠道：`serverchan`、`feishu`、`webhook` |
| `job.enabled` | GPU 空闲后是否运行任务 |
| `job.command` | 命令、Python 脚本、shell 脚本或命令序列 |
| `job.gpus` | 要监控并分配给任务的 GPU 序号 |
| `job.working_dir` | 任务运行目录 |
| `job.cooldown_minutes` | 管理员常驻模式下的任务冷却时间 |
| `job.log_dir` | 每次任务的日志目录，默认 `./runtime/jobs` |

旧字段仍兼容，例如 `send_key`、`check_interval`、`cooldown_seconds`、`watch_gpu_indices`、`auto_run_job`。
