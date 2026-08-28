"""Singleton lock, pid forensics, and the handoff successor.

Carved move-only from the dispatcher monolith (B4, 2026-08-29); bodies are
verbatim — see git history of core/dispatcher.py for provenance.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import typing as _typing
import shutil
import sqlite3
from dataclasses import dataclass, field
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime
from pathlib import Path

from ... import agent, pipeline
from .. import config, fsutil, gateway_health, network_wait, quota, quota_wait
from ..admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                         DENY_TARGET_COOLED, admission)
from ...state import db, thresholds, transitions, tree
from ...state import intent as intent_mod
from ...state import failures as _failures
from ...state import groups as _groups
from ...quality import prune, verify


def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check. POSIX: os.kill(pid, 0); Windows:
    OpenProcess + GetExitCodeProcess.

    Note: On Windows, os.kill(pid, 0) raises SystemError because sig
    0 isn't a real Windows signal — Python's os.kill on Windows only
    handles termination signals via TerminateProcess.

    Windows kernel keeps the Process object live for any handle holder
    even AFTER the process has terminated, so OpenProcess succeeds on
    a freshly-killed PID. GetExitCodeProcess distinguishes "still
    running" (STILL_ACTIVE=259) from "terminated but handle-zombie".
    Without this check, the singleton lock would refuse new daemons
    for any PID the OS hasn't recycled yet."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            exit_code = ctypes.c_uint32(0)
            ok = kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _proc_start_time(pid: int) -> "float | None":
    """psutil process create-time for `pid` (epoch seconds), or None if the
    process is gone / its start-time is unreadable. Paired with the PID it
    forms a reuse-proof process-instance identity for the singleton lock."""
    try:
        import psutil
        return psutil.Process(pid).create_time()
    except Exception:
        return None


def _cmdline_is_daemon(pid: int) -> "bool | None":
    """True / False iff the live process at `pid` is / isn't an asterism
    dispatcher (`python -m Tooling.core.cli run …` or the `asterism run`
    console script); None if its command line can't be read. The fallback
    identity signal for a legacy pid-only lock that has no recorded
    start-time."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        argv = psutil.Process(pid).cmdline()
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None
    joined = " ".join(argv)
    if ("Tooling.core.cli" in joined
            or "core/cli" in joined or "core\\cli" in joined):
        return True
    if argv and "run" in argv:
        exe = argv[0].lower().replace("\\", "/").rsplit("/", 1)[-1]
        if exe.startswith("asterism"):
            return True
    return False


def _lock_held_by_live_daemon(pid: int, stored_start: "float | None") -> bool:
    """True iff `pid` is the SAME live daemon instance that wrote the lock —
    NOT merely a live PID. Guards against PID REUSE: after a daemon crashes
    without releasing its lock, the OS can hand its PID to an unrelated live
    process (observed 2026-06-15 — a crashed daemon's PID was reused by the
    editor, so the bare-liveness lock blocked every restart). A (pid,
    start-time) pair identifies a process instance, so a reused PID — alive
    but with a different start-time — reads as stale.

    `stored_start` is the start-time recorded in the lock (None for a legacy
    pid-only lock). When absent or unreadable, fall back to a command-line
    signature; if neither signal can be read, conservatively treat a live PID
    as the daemon so two daemons never share one DB (the disaster the lock
    exists to prevent)."""
    if not _pid_alive(pid):
        return False
    if stored_start is not None:
        live = _proc_start_time(pid)
        if live is not None:
            return abs(live - stored_start) < 1.0
        # start-time unreadable — fall through to the cmdline signal.
    sig = _cmdline_is_daemon(pid)
    if sig is None:
        return True  # can't introspect a live PID — conservative (block)
    return sig


def _acquire_singleton_lock(workspace: Path) -> Path | None:
    """Refuse to start if another daemon is already running on this
    workspace. Two daemons sharing one DB silently dispatch the same
    goal twice, write conflicting strategy rows, and clobber each
    other's verify_strategy state. Caught in the wild when a stray
    `&` background invocation overlapped with a fresh `run`.

    Mechanism: PID file at `.asterism/daemon.pid` holding `pid\\nstart_time`.
    On startup:
      - if file missing → create, return path
      - if it names the SAME live process instance (pid + start-time, or a
        daemon command line for a legacy pid-only lock) → return None
        (caller exits)
      - if it names a dead PID, or a REUSED PID now belonging to a different
        process → stale, overwrite. (Bare liveness alone is fooled by PID
        reuse — 2026-06-15: a crashed daemon's PID became the editor's,
        blocking every restart.)

    Returned path should be `.unlink(missing_ok=True)` at shutdown.
    """
    asterism_dir = workspace / ".asterism"
    asterism_dir.mkdir(parents=True, exist_ok=True)
    pid_file = asterism_dir / "daemon.pid"
    my_pid = os.getpid()

    if pid_file.exists():
        existing = -1
        stored_start: "float | None" = None
        try:
            parts = pid_file.read_text(encoding="utf-8").split("\n")
            existing = int(parts[0].strip())
            if len(parts) > 1 and parts[1].strip():
                stored_start = float(parts[1].strip())
        except (OSError, ValueError):
            existing = -1
        if (existing > 0 and existing != my_pid
                and _lock_held_by_live_daemon(existing, stored_start)):
            print(f"[dispatcher] another daemon (pid={existing}) is "
                  f"already running on this workspace. Kill it or wait "
                  f"for it to exit, then retry. (lock: {pid_file})",
                  file=sys.stderr, flush=True)
            return None

    my_start = _proc_start_time(my_pid)
    pid_file.write_text(
        f"{my_pid}\n{my_start if my_start is not None else ''}",
        encoding="utf-8")
    return pid_file


def stop_file_path(workspace: Path) -> Path:
    """Graceful-stop signal (frontend charter §5-3): `asterism daemon
    stop` creates it; the tick loop stops spawning, drains in-flight
    workers, and exits cleanly — the mechanized form of the operator's
    'never kill a daemon with in-flight work' discipline."""
    return workspace / ".asterism" / "daemon.stop"


def _spawn_handoff_successor(workspace: Path, scope: "str | None") -> None:
    """Spawn the drift-handoff waiter: a detached `daemon start
    --wait-lock` that parks until THIS daemon's singleton lock frees,
    then boots a fresh daemon (current code, same scope) through
    daemon_start's usual relay. Must break away from our kill-on-close
    Job Object or it dies with us; best-effort — a failed spawn just
    means the operator restarts by hand (the drain already happened)."""
    import subprocess
    from .. import process_group
    argv = [sys.executable, "-m", "Tooling.core.cli", "daemon", "start",
            "--wait-lock", "120"]
    if scope:
        argv += ["--scope", scope]
    flags = 0
    kwargs: dict = {}
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                 | process_group.breakaway_creationflags())
    else:
        kwargs["start_new_session"] = True
    try:
        # Waiter output goes to a logfile, not DEVNULL: the 2026-07-13
        # 21:01 handoff died without a trace (no successor log, no
        # process, nothing to autopsy) — whatever the waiter prints
        # (its REFUSED reason, a traceback) is the only evidence the
        # next failure will leave.
        logs_dir = workspace / ".asterism" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        waiter_log = open(logs_dir / "handoff-waiter.log", "ab")
        waiter_log.write(
            f"\n=== handoff waiter spawned {db.now()} ===\n".encode())
        waiter_log.flush()
        subprocess.Popen(argv, cwd=str(workspace),
                         stdout=waiter_log,
                         stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL,
                         creationflags=flags, **kwargs)
    except OSError as e:
        print(f"[dispatcher] handoff spawn failed ({e}) — restart the "
              f"daemon by hand (`asterism daemon start`)", flush=True)


def scope_mismatch_reason(workspace: Path,
                          scope: str) -> "str | None":
    """#158 pre-flight: None when `scope` (SQL LIKE, the same pattern
    dispatch filters on) matches at least one REGISTERED problem;
    otherwise a teaching refusal message.

    A no-match scope can never dispatch anything — the daemon boots,
    patrols an empty set forever, and the idle is indistinguishable
    from health (08-04 SLC: `reset` deletes the problems row; two
    restarts idled ~20min before the missing `init` was noticed).
    Registration — not goals — is the right predicate: a freshly
    init'd problem has no goals yet but is legitimately dispatchable
    (the Strategist bootstraps it).

    Read-only raw connection on purpose: this runs in the START
    caller's process while a daemon may be live, and a pre-flight must
    neither write nor auto-migrate (`db.connect` migrates)."""
    import sqlite3 as _sqlite3
    db_file = workspace / db.DB_PATH
    try:
        conn = _sqlite3.connect(
            f"file:{db_file.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM problems WHERE name LIKE ?",
                (scope,)).fetchone()[0]
        finally:
            conn.close()
    except _sqlite3.OperationalError:
        # No DB file / no problems table — same answer as 0 matches:
        # nothing is registered under this scope.
        n = 0
    if n:
        return None
    return (f"REFUSING to start: --scope {scope!r} matches no registered "
            f"problem — dispatch would idle forever and look healthy. "
            f"If this problem was just reset, `asterism reset` deletes "
            f"its registration: run `asterism init <problem>` first, "
            f"then start again (or fix the scope pattern).")


