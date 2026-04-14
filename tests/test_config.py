from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from gpu_idle_notifier.config import load_config

WORKSPACE_TEMP_DIR = Path(__file__).resolve().parents[1] / ".tmp-tests"


def _temp_file(name: str) -> Path:
    WORKSPACE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_TEMP_DIR / f"{name}-{int(time.time() * 1000)}.json"


class ConfigTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
