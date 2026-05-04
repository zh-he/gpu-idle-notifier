from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType


class SingletonLock:
    """Process-level lock to ensure only one watcher instance is running."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._file = None

    def __enter__(self) -> "SingletonLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.lock_path.open("w+", encoding="utf-8")

        try:
            if os.name == "nt":
                import msvcrt

                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._file.close()
            self._file = None
            raise RuntimeError("Another watcher instance is already running.") from exc

        self._file.seek(0)
        self._file.write(str(os.getpid()))
        self._file.truncate()
        self._file.flush()

    def release(self) -> None:
        if not self._file:
            return

        try:
            if os.name == "nt":
                import msvcrt

                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._file.close()
            self._file = None
