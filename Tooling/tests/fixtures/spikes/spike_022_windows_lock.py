"""spike-022: fcntl on Windows — does it exist? what's the alternative?

P6 needs cross-OS file/region locking for Library promotion + scheduler
liveness (impl §3.1, §6 schedulers heartbeat). Tests:
  (a) confirm fcntl is unavailable on Windows
  (b) confirm msvcrt.locking is available + functional
  (c) confirm SQLite advisory lock (BEGIN EXCLUSIVE) works as a
      portable fallback

Run:
    cd /d/Asterism && python Tooling/tests/fixtures/spikes/spike_022_windows_lock.py
"""
from __future__ import annotations

import os
import platform
import sqlite3
import sys
import tempfile
import time


def probe_fcntl() -> dict:
    try:
        import fcntl  # noqa
        return {"available": True, "module": "fcntl"}
    except ImportError as e:
        return {"available": False, "error": str(e)}


def probe_msvcrt_locking() -> dict:
    try:
        import msvcrt
    except ImportError as e:
        return {"available": False, "error": str(e)}

    if not hasattr(msvcrt, "locking"):
        return {"available": False, "error": "msvcrt has no `locking` attr"}

    # Try real lock+unlock cycle on a tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        # Write a few bytes so locking() has something to lock
        tmp.write(b"x" * 8)
        tmp.flush()
        # msvcrt.locking requires file in binary mode + seek to 0
        tmp.seek(0)
        try:
            msvcrt.locking(tmp.fileno(), msvcrt.LK_NBLCK, 8)
            locked = True
            msvcrt.locking(tmp.fileno(), msvcrt.LK_UNLCK, 8)
        except OSError as e:
            return {"available": True, "lock_error": str(e)}
    finally:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return {"available": True, "lock_works": locked}


def probe_sqlite_exclusive() -> dict:
    """SQLite advisory lock via BEGIN EXCLUSIVE — portable, used by
    Asterism's existing scheduler.events table for IPC."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        conn1 = sqlite3.connect(tmp.name)
        conn1.execute("CREATE TABLE t (x INT)")
        conn1.commit()

        # Open a second connection to test contention
        conn2 = sqlite3.connect(tmp.name, timeout=0.5)

        # conn1 acquires EXCLUSIVE
        conn1.execute("BEGIN EXCLUSIVE")
        conn1.execute("INSERT INTO t VALUES (1)")

        # conn2 tries to acquire — should hit "database is locked"
        try:
            conn2.execute("BEGIN EXCLUSIVE")
            second_acquired = True
        except sqlite3.OperationalError as e:
            second_acquired = False
            err = str(e)
        else:
            err = None

        conn1.commit()
        conn1.close()
        conn2.close()

        return {
            "available": True,
            "exclusive_blocks_other_connection": not second_acquired,
            "error_msg": err,
            "sqlite_version": sqlite3.sqlite_version,
        }
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def main() -> int:
    print(f"platform: {platform.system()} {platform.release()}")
    print(f"python:   {sys.version_info[:3]}")
    print()

    fcntl_res = probe_fcntl()
    print(f"fcntl: {fcntl_res}")

    msvcrt_res = probe_msvcrt_locking()
    print(f"msvcrt.locking: {msvcrt_res}")

    sqlite_res = probe_sqlite_exclusive()
    print(f"sqlite BEGIN EXCLUSIVE: {sqlite_res}")

    print()
    print("Decision suggestion (D-22-1 candidate):")
    if not fcntl_res.get("available") and msvcrt_res.get("lock_works"):
        print("  - Windows: msvcrt.locking for region locks on regular files")
    if sqlite_res.get("exclusive_blocks_other_connection"):
        print("  - Cross-OS portable: sqlite BEGIN EXCLUSIVE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
