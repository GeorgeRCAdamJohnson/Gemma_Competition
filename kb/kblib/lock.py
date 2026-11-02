"""Exclusive build lock (design §15.3).

Uses O_CREAT|O_EXCL to create KB/.build.lock. Liveness on Windows is checked
with ctypes (OpenProcess), never os.kill (which terminates on Windows). A stale
lock (dead pid, or older than max age) is reclaimed. --lock-wait-s is honoured
and cut by --deadline-s.
"""
from __future__ import annotations

import json
import os
import pathlib
import time

# A build runs in well under a minute on current data; a lock older than this is
# from a crashed/killed build (pids can be reused on Windows, so age is the
# reliable staleness signal and liveness is only a fast-path).
STALE_AGE_S = 90.0


_STILL_ACTIVE = 259


def _pid_alive(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return pid == os.getpid()
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong(0)
            if k32.GetExitCodeProcess(h, ctypes.byref(code)):
                # a finished process reports its real exit code, not STILL_ACTIVE
                return code.value == _STILL_ACTIVE
            return True
        finally:
            k32.CloseHandle(h)
    except Exception:
        # Non-Windows / unavailable: treat as dead so a leftover lock is reclaimed.
        return False


class BuildLock:
    def __init__(self, kb_root: pathlib.Path):
        self.path = kb_root / ".build.lock"
        self.held = False

    def _is_stale(self) -> bool:
        try:
            meta = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return True
        if time.time() - meta.get("created", 0) > STALE_AGE_S:
            return True
        return not _pid_alive(int(meta.get("pid", -1)))

    def acquire(self, wait_s: float = 0.0, deadline: float | None = None) -> float:
        start = time.time()
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(
                    fd,
                    json.dumps({"pid": os.getpid(), "created": time.time()}).encode(),
                )
                os.close(fd)
                self.held = True
                return time.time() - start
            except FileExistsError:
                if self._is_stale():
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                now = time.time()
                if now - start >= wait_s:
                    raise TimeoutError("build lock held by a live process")
                if deadline is not None and now >= deadline:
                    raise TimeoutError("deadline reached while waiting for lock")
                time.sleep(0.5)

    def release(self) -> None:
        if self.held and self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass
        self.held = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
