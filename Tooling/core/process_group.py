"""Windows Job Object so the daemon's spawned process tree (claude / lake / lean
/ per-spawn LSP) is reaped automatically when the daemon dies — for ANY reason,
including a hard `taskkill /F` with no `/T`. This replaces the manual
orphan-cleanup ritual and removes the documented self-harm footgun where a
name+time `broad-kill` of orphan `claude.exe` also kills the operator's own
conversation process (CLAUDE.md rule 8).

Mechanism: at daemon startup we create a Job Object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and assign the CURRENT process to it. On
Windows a child process is auto-assigned to its parent's job, so every later
spawn (and its descendants — lake → lean) lands in the same job. The daemon
holds the only job handle; when the daemon process exits the OS closes that
handle and terminates the whole job tree.

The LONG-LIVED LSP gateway is the one exception: it is reused across daemon
restarts (warming Mathlib costs minutes — `lsp/lifecycle.start_gateway`), so it
must SURVIVE the daemon's death. The job is created with
`JOB_OBJECT_LIMIT_BREAKAWAY_OK` and the gateway is spawned with
`CREATE_BREAKAWAY_FROM_JOB` (gated on `should_breakaway()`), so it escapes the
job while every ephemeral agent spawn stays in it.

Pure `ctypes` — no pywin32 dependency. No-op on non-Windows (the daemon targets
win32; a POSIX `os.setpgrp` + process-group kill equivalent is left for when a
POSIX daemon is needed). Every failure is soft: the caller falls back to the
existing orphan-sweep / atexit safety net, never fatal.
"""
from __future__ import annotations

import sys

# Holds the job HANDLE for the whole process lifetime. This must stay referenced:
# if it were GC'd/closed, KILL_ON_JOB_CLOSE would fire and kill us immediately.
_job_handle = None
_assigned = False

# winnt.h
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
_JobObjectExtendedLimitInformation = 9


def _build_structs(ctypes, wintypes):
    """The two job-info structs, ULONG_PTR fields as c_size_t (32/64-safe)."""
    class _BASIC(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _EXT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BASIC),
            ("IoInfo", _IO),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]
    return _EXT


def assign_self_to_kill_on_close_job() -> bool:
    """Create a kill-on-close (+ breakaway-ok) Job Object and assign THIS process
    to it, so all later child spawns die when this process dies. Idempotent: a
    second call is a no-op once assigned. Returns True on success; False (soft)
    when unsupported or the OS refuses — the caller keeps the orphan-sweep net."""
    global _job_handle, _assigned
    if sys.platform != "win32":
        return False
    if _assigned:
        return True
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.GetCurrentProcess.restype = wintypes.HANDLE

        job = k32.CreateJobObjectW(None, None)
        if not job:
            return False
        ext_cls = _build_structs(ctypes, wintypes)
        info = ext_cls()
        info.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | _JOB_OBJECT_LIMIT_BREAKAWAY_OK)
        if not k32.SetInformationJobObject(
                job, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            return False
        # AssignProcessToJobObject can fail with ACCESS_DENIED if we already sit
        # in a non-nestable job (pre-Win8). Win8+ nests jobs, so this normally
        # succeeds; on failure we leave _assigned False and fall back.
        if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
            return False
        _job_handle = job          # keep the handle alive for process lifetime
        _assigned = True
        return True
    except Exception:  # noqa: BLE001 — any ctypes/OS fault → soft fallback
        return False


def should_breakaway() -> bool:
    """True iff this process is in our kill-on-close job, so a child that must
    OUTLIVE the daemon (the reusable LSP gateway) may safely be spawned with
    `CREATE_BREAKAWAY_FROM_JOB`. False otherwise — passing the breakaway flag
    when NOT in a breakaway-ok job makes CreateProcess fail, so callers must
    gate on this."""
    return _assigned


def breakaway_creationflags() -> int:
    """`subprocess.Popen(creationflags=...)` value for a child that must survive
    the daemon: `CREATE_BREAKAWAY_FROM_JOB` when we hold a breakaway-ok job, else
    0 (no-op / non-Windows)."""
    if not _assigned or sys.platform != "win32":
        return 0
    import subprocess
    return getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)


_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100


_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008


def create_capped_job(per_process_mb: int, *, max_processes: int = 0):
    """A kill-on-close Job Object with a PER-PROCESS commit cap, for the
    gateway's `lake serve → lean --server → lean --worker` tree.

    Two holes it closes at once (2026-08-08 post-mortem — one lean
    worker reached 102 GB of commit and took the workstation down):

      * No ceiling: kernel reduction does not count heartbeats, so a
        diverging `decide`/whnf allocates ~30 MB/s until the machine
        dies. With the cap, allocations beyond it FAIL inside that one
        process — the worker dies loudly, siblings and the OS live.
      * Unreachable orphans: `taskkill /T` walks the CURRENT
        parent-child chain, so a worker whose parent died first is
        re-parented and survives the sweep (it outlived 21 backend
        restarts that night). Job membership is not affected by
        re-parenting — `terminate_job` reaps every member, orphan or
        not, and KILL_ON_JOB_CLOSE backstops a dropped handle.

    `max_processes` (0 = unlimited) additionally caps how many processes
    may live in the job at once. The gateway tree needs many; the compute
    sandbox needs exactly one, and a hard OS-level 1 there means a
    `subprocess` that somehow got past the audit hook still cannot start.

    Returns the job handle (keep it referenced!), or None off-Windows /
    on any OS refusal — callers keep the taskkill path as fallback."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        ext_cls = _build_structs(ctypes, wintypes)
        info = ext_cls()
        flags = (_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                 | _JOB_OBJECT_LIMIT_PROCESS_MEMORY)
        if max_processes > 0:
            flags |= _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            info.BasicLimitInformation.ActiveProcessLimit = int(max_processes)
        info.BasicLimitInformation.LimitFlags = flags
        info.ProcessMemoryLimit = int(per_process_mb) * 1024 * 1024
        if not k32.SetInformationJobObject(
                job, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return None
        return job
    except Exception:  # noqa: BLE001 — soft fallback, taskkill still runs
        return None


def assign_to_job(job, proc) -> bool:
    """Assign a freshly-Popen'd child to `job`. Its own descendants then
    inherit membership automatically. Soft-fails to False (the child
    keeps running unmanaged; callers keep their fallback kill path)."""
    if job is None or sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE]
        return bool(k32.AssignProcessToJobObject(
            job, int(proc._handle)))  # noqa: SLF001 — Popen's real handle
    except Exception:  # noqa: BLE001
        return False


def terminate_job(job) -> bool:
    """TerminateJobObject + CloseHandle: reap EVERY member, including
    re-parented orphans `taskkill /T` cannot see. Idempotent-ish; soft."""
    if job is None or sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        ok = bool(k32.TerminateJobObject(job, 1))
        k32.CloseHandle(job)
        return ok
    except Exception:  # noqa: BLE001
        return False


def no_window_creationflags() -> int:
    """`creationflags` addend that stops a console-subsystem child from
    popping a visible console window when its parent has none (the
    detached daemon): CREATE_NO_WINDOW on Windows, 0 elsewhere. Callers
    must OR this with any other flags (never assign over breakaway)."""
    if sys.platform != "win32":
        return 0
    import subprocess
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
