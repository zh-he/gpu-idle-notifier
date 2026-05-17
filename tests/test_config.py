from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from gpu_idle_notifier.config import load_config

WORKSPACE_TEMP_DIR = Path(__file__).resolve().parents[1] / ".tmp-tests"


def _temp_file(name: str) -> Path:
    WORKSPACE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_TEMP_DIR / f"{name}-{int(time.time() * 1000)}.json"


class ConfigTests(unittest.TestCase):
    def test_default_check_interval_and_idle_hits(self) -> None:
        config_path = _temp_file("config-defaults")
        try:
            config_path.write_text(json.dumps({}), encoding="utf-8")

            cfg = load_config(config_path)
            self.assertEqual(cfg.mode, "once")
            self.assertEqual(cfg.check_interval, 20 * 60)
            self.assertEqual(cfg.idle_consecutive_hits, 3)
            self.assertEqual(cfg.idle_notify_max_count, 3)
            self.assertEqual(cfg.cooldown_seconds, 30 * 60)
        finally:
            config_path.unlink(missing_ok=True)

    def test_load_config_from_json(self) -> None:
        config_path = _temp_file("config-load")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "server_name": "Test-Server",
                        "auto_run_job": {
                            "enabled": True,
                            "command": ["python", "job.py"],
                            "cooldown_seconds": 30,
                        },
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.server_name, "Test-Server")
            self.assertTrue(cfg.auto_run_job.enabled)
            self.assertEqual(cfg.auto_run_job.command, ["python", "job.py"])
            self.assertEqual(cfg.auto_run_job.cooldown_seconds, 30)
        finally:
            config_path.unlink(missing_ok=True)

    def test_parse_check_interval_minutes(self) -> None:
        config_path = _temp_file("config-minutes")
        try:
            config_path.write_text(
                json.dumps({"check_interval_minutes": 5}),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.check_interval, 300)
        finally:
            config_path.unlink(missing_ok=True)

    def test_legacy_check_interval_seconds_still_works(self) -> None:
        config_path = _temp_file("config-seconds")
        try:
            config_path.write_text(
                json.dumps({"check_interval": 60, "check_interval_minutes": 20}),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.check_interval, 60)
        finally:
            config_path.unlink(missing_ok=True)

    def test_parse_cooldown_minutes(self) -> None:
        config_path = _temp_file("config-cooldown-minutes")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "cooldown_minutes": 45,
                        "job": {
                            "enabled": True,
                            "command": "python job.py",
                            "cooldown_minutes": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.cooldown_seconds, 45 * 60)
            self.assertEqual(cfg.auto_run_job.cooldown_seconds, 10 * 60)
        finally:
            config_path.unlink(missing_ok=True)

    def test_legacy_cooldown_seconds_still_works(self) -> None:
        config_path = _temp_file("config-cooldown-seconds")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "cooldown_seconds": 90,
                        "cooldown_minutes": 45,
                        "auto_run_job": {
                            "enabled": True,
                            "command": ["python", "job.py"],
                            "cooldown_seconds": 30,
                            "cooldown_minutes": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.cooldown_seconds, 90)
            self.assertEqual(cfg.auto_run_job.cooldown_seconds, 30)
        finally:
            config_path.unlink(missing_ok=True)

    def test_parse_daemon_mode(self) -> None:
        config_path = _temp_file("config-mode")
        try:
            config_path.write_text(json.dumps({"mode": "daemon"}), encoding="utf-8")

            cfg = load_config(config_path)
            self.assertEqual(cfg.mode, "daemon")
        finally:
            config_path.unlink(missing_ok=True)

    def test_invalid_mode_is_rejected(self) -> None:
        config_path = _temp_file("config-invalid-mode")
        try:
            config_path.write_text(json.dumps({"mode": "admin"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "mode must be one of"):
                load_config(config_path)
        finally:
            config_path.unlink(missing_ok=True)

    def test_invalid_idle_notify_max_count_is_rejected(self) -> None:
        config_path = _temp_file("config-invalid-idle-notify-max")
        try:
            config_path.write_text(json.dumps({"idle_notify_max_count": 0}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "idle_notify_max_count must be > 0"):
                load_config(config_path)
        finally:
            config_path.unlink(missing_ok=True)

    def test_parse_string_command(self) -> None:
        config_path = _temp_file("config-command")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "auto_run_job": {
                            "enabled": True,
                            "command": "python train.py --epochs 2",
                        }
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.auto_run_job.command, ["python", "train.py", "--epochs", "2"])
        finally:
            config_path.unlink(missing_ok=True)

    def test_parse_string_bool_values(self) -> None:
        config_path = _temp_file("config-bool")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "recover_notify": "false",
                        "threshold": {"no_proc": "true"},
                        "auto_run_job": {
                            "enabled": "true",
                            "command": ["python", "job.py"],
                            "notify_on_start": "0",
                            "notify_on_finish": "1",
                        },
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertFalse(cfg.recover_notify)
            self.assertTrue(cfg.threshold.no_proc)
            self.assertTrue(cfg.auto_run_job.enabled)
            self.assertFalse(cfg.auto_run_job.notify_on_start)
            self.assertTrue(cfg.auto_run_job.notify_on_finish)
        finally:
            config_path.unlink(missing_ok=True)

    def test_send_key_env_override_has_priority(self) -> None:
        config_path = _temp_file("config-sendkey")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "send_key": "from-config",
                        "auto_run_job": {"enabled": False},
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"GPU_IDLE_NOTIFIER_SEND_KEY": "from-env"}, clear=False):
                cfg = load_config(config_path)
                self.assertEqual(cfg.send_key, "from-env")
        finally:
            config_path.unlink(missing_ok=True)

    def test_minimal_job_config_maps_to_auto_run_job(self) -> None:
        config_path = _temp_file("config-job")
        try:
            config_path.write_text(
                json.dumps(
                    {
                        "server_name": "Lab-Server",
                        "notify": {
                            "providers": [
                                {"type": "serverchan", "send_key": "SCT-test"},
                                {"type": "feishu", "webhook": "https://example.test/hook"},
                            ]
                        },
                        "job": {
                            "enabled": True,
                            "command": "llamafactory-cli train config.yaml",
                            "working_dir": "/tmp/llamafactory",
                            "gpus": [0, 1, 2, 3],
                            "log_dir": "./runtime/jobs",
                        },
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(cfg.watch_gpu_indices, [0, 1, 2, 3])
            self.assertEqual(cfg.min_idle_gpus, 4)
            self.assertTrue(cfg.auto_run_job.enabled)
            self.assertEqual(
                cfg.auto_run_job.command,
                ["llamafactory-cli", "train", "config.yaml"],
            )
            self.assertEqual(cfg.auto_run_job.min_idle_gpus, 4)
            self.assertTrue(cfg.auto_run_job.run_once_per_idle)
            self.assertEqual(len(cfg.notify_providers), 2)
            self.assertEqual(cfg.notify_providers[0].type, "serverchan")
            self.assertEqual(cfg.notify_providers[1].type, "feishu")
        finally:
            config_path.unlink(missing_ok=True)

    def test_legacy_send_key_becomes_serverchan_provider(self) -> None:
        config_path = _temp_file("config-legacy-notify")
        try:
            config_path.write_text(
                json.dumps({"send_key": "SCT-legacy", "auto_run_job": {"enabled": False}}),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            self.assertEqual(len(cfg.notify_providers), 1)
            self.assertEqual(cfg.notify_providers[0].type, "serverchan")
            self.assertEqual(cfg.notify_providers[0].send_key, "SCT-legacy")
        finally:
            config_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
