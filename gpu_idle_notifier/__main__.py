from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from .config import load_config
from .lock import SingletonLock
from .logging_utils import setup_logging
from .watcher import GPUWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GPU idle notifier")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to JSON config file. If not set, defaults or GPU_IDLE_NOTIFIER_CONFIG are used.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 1

    setup_logging(config.log_file)
    logging.info("Config loaded. state_file=%s", config.state_file)

    try:
        with SingletonLock(config.lock_file):
            watcher = GPUWatcher(config)
            watcher.run()
        return 0
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
