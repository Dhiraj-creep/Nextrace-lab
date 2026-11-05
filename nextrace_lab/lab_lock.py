"""Cross-Process Lab Execution Lock (Stage 1E).

Protects all state-mutating operations across CLI and Streamlit dashboard:
- starting/stopping services
- applying/resetting faults
- running diagnostic investigations that mutate runtime state
- running experiment suites

Lock semantics:
- Exclusive lock file at `var/runtime/lab_execution.lock` created atomically with O_CREAT | O_EXCL.
- Records holder PID, UTC timestamp, monotonic acquisition time, operation name, and holder label.
- Fails fast with `LabLockBusyError` when another live process holds the lock.
- Recovers stale locks ONLY when the recorded PID is verifiably not running AND the lock age exceeds
  `stale_lock_timeout_sec` (default 1800s / 30m, configurable for tests).
- Supports re-entrant acquisition within the same PID/thread so an experiment suite can hold the outer
  lock while calling `apply_fault` / `reset_faults` internally.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable, Iterator, Optional

from nextrace_lab.logging_utils import utc_now_iso

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "var" / "runtime"
DEFAULT_LOCK_FILE = RUNTIME_DIR / "lab_execution.lock"

_THREAD_LOCAL_DEPTH = threading.local()


class LabLockBusyError(RuntimeError):
    """Raised when a state-mutating lab operation is attempted while another live process holds the lock."""

    def __init__(self, message: str, holder_metadata: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.holder_metadata = holder_metadata or {}


def is_pid_alive(pid: Optional[int]) -> bool:
    """Check whether a host process with the given PID is currently alive."""
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            return str(pid) in res.stdout
        except Exception:
            return True  # Be conservative if tasklist fails
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False


class LabExecutionLock:
    """Cross-process exclusive lock for NexTrace lab mutations."""

    def __init__(
        self,
        operation: str,
        *,
        holder: str = "cli",
        lock_path: Path = DEFAULT_LOCK_FILE,
        stale_lock_timeout_sec: float = 1800.0,
        pid_override: Optional[int] = None,
        pid_checker: Callable[[Optional[int]], bool] = is_pid_alive,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.operation = operation
        self.holder = holder
        self.lock_path = Path(lock_path)
        self.stale_lock_timeout_sec = stale_lock_timeout_sec
        self.pid = pid_override if pid_override is not None else os.getpid()
        self.pid_checker = pid_checker
        self.time_fn = time_fn
        self._acquired_file = False
        self._reentrant = False

    def _get_reentrant_key(self) -> str:
        return f"{self.lock_path.resolve()}::{self.pid}"

    def _read_existing_metadata(self) -> dict[str, Any]:
        try:
            if not self.lock_path.exists():
                return {}
            with open(self.lock_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def acquire(self) -> dict[str, Any]:
        """Acquire the lock atomically or raise LabLockBusyError."""
        key = self._get_reentrant_key()
        depths: dict[str, int] = getattr(_THREAD_LOCAL_DEPTH, "depths", {})
        if depths.get(key, 0) > 0 and self.pid == os.getpid():
            depths[key] = depths[key] + 1
            _THREAD_LOCAL_DEPTH.depths = depths
            self._reentrant = True
            return self._read_existing_metadata()

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        now_epoch = self.time_fn()
        metadata = {
            "pid": self.pid,
            "holder": self.holder,
            "operation": self.operation,
            "acquired_at_utc": utc_now_iso(),
            "acquired_epoch_sec": now_epoch,
        }

        for _attempt in range(2):
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    payload = json.dumps(metadata, indent=2).encode("utf-8")
                    os.write(fd, payload)
                finally:
                    os.close(fd)
                self._acquired_file = True
                if self.pid == os.getpid():
                    depths[key] = 1
                    _THREAD_LOCAL_DEPTH.depths = depths
                return metadata
            except FileExistsError:
                existing = self._read_existing_metadata()
                holder_pid = existing.get("pid")
                acquired_epoch = float(existing.get("acquired_epoch_sec", 0.0) or 0.0)
                age_sec = max(0.0, now_epoch - acquired_epoch) if acquired_epoch > 0 else 0.0
                pid_alive = self.pid_checker(holder_pid)

                # Conservative stale lock recovery: ONLY recover if PID is dead AND age > threshold
                if (not pid_alive) and age_sec >= self.stale_lock_timeout_sec:
                    try:
                        self.lock_path.unlink()
                        continue
                    except OSError:
                        pass

                holder_desc = (
                    f"pid={holder_pid} ({'alive' if pid_alive else 'dead'}), "
                    f"holder={existing.get('holder', 'unknown')}, "
                    f"operation={existing.get('operation', 'unknown')}, "
                    f"acquired_at={existing.get('acquired_at_utc', 'unknown')}, "
                    f"age_sec={age_sec:.1f}"
                )
                raise LabLockBusyError(
                    f"Cannot execute '{self.operation}': LabExecutionLock is currently held by [{holder_desc}].",
                    holder_metadata=existing,
                )

        existing = self._read_existing_metadata()
        raise LabLockBusyError(
            f"Cannot execute '{self.operation}': LabExecutionLock at {self.lock_path} could not be acquired.",
            holder_metadata=existing,
        )

    def release(self) -> None:
        """Release the lock if held by this instance."""
        key = self._get_reentrant_key()
        depths: dict[str, int] = getattr(_THREAD_LOCAL_DEPTH, "depths", {})
        if self._reentrant:
            if depths.get(key, 0) > 1:
                depths[key] -= 1
            self._reentrant = False
            return

        if self._acquired_file:
            try:
                existing = self._read_existing_metadata()
                if not existing or existing.get("pid") == self.pid:
                    if self.lock_path.exists():
                        self.lock_path.unlink()
            except OSError:
                pass
            finally:
                self._acquired_file = False
                if self.pid == os.getpid():
                    depths.pop(key, None)
                    _THREAD_LOCAL_DEPTH.depths = depths

    def __enter__(self) -> dict[str, Any]:
        return self.acquire()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


@contextmanager
def acquire_lab_lock(
    operation: str,
    *,
    holder: str = "cli",
    lock_path: Path = DEFAULT_LOCK_FILE,
    stale_lock_timeout_sec: float = 1800.0,
) -> Iterator[dict[str, Any]]:
    """Context manager helper for acquiring the cross-process LabExecutionLock."""
    lock = LabExecutionLock(
        operation=operation,
        holder=holder,
        lock_path=lock_path,
        stale_lock_timeout_sec=stale_lock_timeout_sec,
    )
    meta = lock.acquire()
    try:
        yield meta
    finally:
        lock.release()


def get_lock_status(lock_path: Path = DEFAULT_LOCK_FILE) -> dict[str, Any]:
    """Inspect current lock status without acquiring or mutating the lock."""
    if not lock_path.exists():
        return {"locked": False, "lock_path": str(lock_path)}
    try:
        with open(lock_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        pid = data.get("pid")
        alive = is_pid_alive(pid)
        age_sec = max(0.0, time.time() - float(data.get("acquired_epoch_sec", time.time())))
        return {
            "locked": True,
            "lock_path": str(lock_path),
            "pid_alive": alive,
            "age_sec": round(age_sec, 2),
            **data,
        }
    except Exception as exc:
        return {"locked": True, "lock_path": str(lock_path), "error": str(exc)}
