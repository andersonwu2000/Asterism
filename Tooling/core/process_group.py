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


def create_capped_job(per_process_mb: "int | None", *,
                      max_processes: int = 0):
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

    `per_process_mb=None` means NO memory ceiling — the job is then only
    a reaper. That is what an agent spawn wants: the reason to put a CLI
    in a job is that `Popen.kill()` reaps the direct child alone, and a
    vendor CLI installed by npm is a `.cmd` shim whose direct child is
    `cmd.exe` (measured 2026-08-15: a killed codex spawn kept working
    for five more minutes and called a gateway tool at 02:34:35, two
    minutes after the framework recorded it dead). Capping such a tree's
    memory would add a failure mode to fix a lifetime bug.

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
        flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if per_process_mb is not None:
            flags |= _JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info.ProcessMemoryLimit = int(per_process_mb) * 1024 * 1024
        if max_processes > 0:
            flags |= _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            info.BasicLimitInformation.ActiveProcessLimit = int(max_processes)
        info.BasicLimitInformation.LimitFlags = flags
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


def kill_process_tree(pid, *, timeout: float = 30.0) -> "tuple[bool, str]":
    """Kill the process `pid` names AND every descendant, by PID.

    The job-object paths above are for a tree THIS process started and
    still holds a handle for. This one is for a tree nobody holds: the
    LSP gateway breaks away from the daemon's job on purpose
    (`lsp/lifecycle.start_gateway` — in production it is reused across
    daemon restarts), so once the daemon is gone the only name left for
    `gateway -> lake serve -> lean --server -> lean --worker` is the pid
    its own presence marker recorded.

    The descendants are enumerated BEFORE anything is killed. On Windows
    a child does not die with its parent, and one whose parent died
    first is re-parented — invisible to a walk that starts at the root,
    which is the blindness `taskkill /T` has (2026-08-08: one orphaned
    worker outlived 21 backend restarts and reached 102 GB). A list
    taken at a single instant cannot go stale that way. The root is
    killed first so it cannot spawn a replacement backend while the
    descendants are being reaped.

    Returns `(gone, detail)`. `gone` is True only when the root and every
    captured descendant have actually left the process table within
    `timeout` — a teardown that reports success it did not achieve is
    the leak it was written to close. Never raises: `detail` carries
    whatever went wrong, in the OS's own words.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False, f"not a pid: {pid!r}"
    try:
        import psutil
    except ImportError:  # pragma: no cover — psutil is a hard dependency
        return _kill_tree_without_psutil(pid)
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return True, f"pid {pid} was already gone"
    except psutil.Error as exc:  # noqa: BLE001 — reported, never raised
        return False, f"pid {pid}: {type(exc).__name__}: {exc}"
    try:
        kin = root.children(recursive=True)
    except psutil.Error:
        kin = []
    victims = [root] + kin
    refused: "list[str]" = []
    for p in victims:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            continue
        except psutil.Error as exc:  # noqa: BLE001 — e.g. AccessDenied
            refused.append(f"{p.pid} ({type(exc).__name__})")
    _gone, alive = psutil.wait_procs(victims, timeout=timeout)
    detail = f"killed pid {pid} + {len(kin)} descendant(s)"
    if refused:
        detail += f"; refused the kill: {', '.join(refused)}"
    if alive:
        return False, (f"{detail}; still alive after {timeout:.0f}s: "
                       + ", ".join(str(p.pid) for p in alive))
    return True, detail


def _kill_tree_without_psutil(pid: int) -> "tuple[bool, str]":
    """Last resort. `taskkill /T` walks the CURRENT parent-child chain,
    so it cannot see a re-parented orphan — that is exactly why psutil
    is the primary path, and why this says so in its own answer."""
    if sys.platform == "win32":
        import subprocess
        r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True,
                           creationflags=no_window_creationflags())
        out = (r.stdout or b"").decode("utf-8", "replace").strip()
        return r.returncode == 0, (
            f"psutil absent — taskkill /T on pid {pid} rc={r.returncode} "
            f"{out}; a re-parented descendant may have survived it")
    import os
    import signal
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True, f"pid {pid} was already gone"
    except OSError as exc:
        return False, f"kill {pid}: {exc}"
    return False, (f"psutil absent — SIGKILL sent to pid {pid} alone; its "
                   f"descendants were not enumerated")


def no_window_creationflags() -> int:
    """`creationflags` addend that stops a console-subsystem child from
    popping a visible console window when its parent has none (the
    detached daemon): CREATE_NO_WINDOW on Windows, 0 elsewhere. Callers
    must OR this with any other flags (never assign over breakaway)."""
    if sys.platform != "win32":
        return 0
    import subprocess
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------------------
# the protocol pipes, taken off the inheritance path
# ---------------------------------------------------------------------------

#: Whatever the fence had to keep alive for the process's lifetime — the
#: null-device handle Windows now calls STD_INPUT, and (on POSIX) the
#: file objects the transport was moved onto. Closing any of it would
#: hand the next child the pipe back.
_fence_keepalive: "list" = []
_fenced = False

_STD_INPUT_HANDLE = -10
_STD_OUTPUT_HANDLE = -11
_STD_ERROR_HANDLE = -12
_HANDLE_FLAG_INHERIT = 0x00000001


def fence_std_handles_from_children() -> bool:
    """Stop this process's OWN stdin/stdout being what a child inherits.

    For a stdio JSON-RPC server (`knowledge/mcp_tools`) those two pipes
    are the protocol, and a child that inherits either is a bug with two
    faces:

      * stdout — anything the child prints lands in the middle of a
        JSON-RPC frame and the client drops the connection. The module
        docstring has said "nothing may be written to stdout" since the
        server shipped; a docstring binds the code we write, not the
        `perl` three levels down a TeX toolchain.
      * stdin — and this one does not need the child to read anything at
        all. MEASURED 2026-09-06 on win32: `latexmk.EXE` spawned with
        stdin inherited was created, loaded 15 modules, and then parked
        its main thread in an Executive wait for the whole 300 s time
        box without executing a line — no `main.log`, no `pdflatex`. It
        woke the instant the parent died. Windows serialises every
        operation on a synchronous file object, so the child's own CRT
        start-up (`GetFileType` on its std handles) queues behind the
        blocking `readline` that `mcp.server.stdio` leaves pending on
        that pipe for the life of the server. Nothing in the child's
        code is involved and no timeout of the child's can help.

    2026-08-11 measured the same wall from the other side ("no
    subprocess started from this stdio server ever runs"), moved
    `compute` to the gateway, and wrote the reason down as a comment.
    `tex_check` shipped a spawn from here on 2026-09-06 and cost the
    Assistant two dead turns. So this is a property of the PROCESS: a
    tool that redirects nothing is correct, and the next tool's author
    does not have to know any of the above.

    After it, `Popen(stdin=None)` gives the child the null device and
    `Popen(stdout=None)` gives it this process's stderr — where a stray
    line is a log entry instead of a protocol violation. `sys.stdin` and
    `sys.stdout` keep reading and writing the real pipes, so the
    transport is untouched.

    Idempotent; soft — False where the OS refuses, and callers that care
    keep passing `stdin=subprocess.DEVNULL` explicitly.
    """
    global _fenced
    if _fenced:
        return True
    try:
        if sys.platform == "win32":
            _fenced = _fence_win32()
        else:
            _fenced = _fence_posix()
    except Exception:  # noqa: BLE001 — a fence that fails is not fatal
        return False
    return _fenced


def _fence_win32() -> bool:
    """`SetStdHandle` writes the PEB's own copy, which is what
    `subprocess` reads (`_get_handles`: `stdin is None` →
    `GetStdHandle(STD_INPUT_HANDLE)`) and what `CreateProcess` copies
    into the child. It does NOT touch the CRT's fd table, so fd 0/1 —
    and therefore `sys.stdin`/`sys.stdout` — still reach the client."""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetStdHandle.restype = wintypes.HANDLE
    k32.GetStdHandle.argtypes = [wintypes.DWORD]
    k32.SetStdHandle.restype = wintypes.BOOL
    k32.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    k32.SetHandleInformation.restype = wintypes.BOOL
    k32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                         wintypes.DWORD]
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD,
                                wintypes.HANDLE]
    # GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ|WRITE, OPEN_EXISTING
    nul = k32.CreateFileW(r"\.\NUL", 0xC0000000, 0x3, None, 3, 0, None)
    if not nul or nul == wintypes.HANDLE(-1).value:
        return False
    # inheritable, or `CreateProcess` hands the child a closed slot
    # instead of the null device and `os.read(0, …)` raises there
    k32.SetHandleInformation(nul, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT)
    err = k32.GetStdHandle(_STD_ERROR_HANDLE)
    if not k32.SetStdHandle(_STD_INPUT_HANDLE, nul):
        return False
    _fence_keepalive.append(nul)
    if err:
        k32.SetStdHandle(_STD_OUTPUT_HANDLE, err)
    return True


def _fence_posix() -> bool:
    """No PEB here: a child inherits fd 0 and fd 1 themselves, so the
    transport has to MOVE. The pipes are duplicated onto private,
    non-inheritable descriptors, `sys.stdin`/`sys.stdout` are rebound to
    those, and fd 0/1 become the null device and this process's stderr."""
    import io
    import os

    kept_in, kept_out = sys.stdin, sys.stdout
    try:
        dup_in = os.dup(0)
        dup_out = os.dup(1)
    except OSError:
        return False
    os.set_inheritable(dup_in, False)
    os.set_inheritable(dup_out, False)
    try:
        kept_out.flush()
    except (OSError, ValueError):
        pass
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    os.dup2(2, 1)
    sys.stdin = io.TextIOWrapper(
        io.BufferedReader(io.FileIO(dup_in, "rb")),
        encoding="utf-8", errors="replace")
    sys.stdout = io.TextIOWrapper(
        io.BufferedWriter(io.FileIO(dup_out, "wb")),
        encoding="utf-8", errors="replace", line_buffering=True)
    # the ORIGINALS still own fd 0/1; dropping them would close what the
    # null device and stderr now sit on
    _fence_keepalive.extend((kept_in, kept_out, sys.stdin, sys.stdout))
    return True
