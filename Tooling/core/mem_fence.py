"""OS memory fence for a cold `lake build` (owner ruling 2026-09-02).

The #234 gate predicted a build's peak and held the lease until
`available` cleared a number. Prediction needs a number, and the number
was wrong twice in one day on one machine: 4.5 sat above the idle
ceiling and saturated every build for 900s; 4.0 was pushed through by a
browser the operator opened. The fence predicts nothing. The build runs
inside a memory limit the OS enforces — a transient user cgroup scope
on Linux, a Job Object on Windows — sized to the room the machine has
RIGHT NOW: measured available minus the ledger's own pressure line,
shared among the builds in flight. Both are live readings; neither is a
knob. A build that outgrows its fence is stopped by the kernel and
reported as `capped`, a structured outcome the caller waits out and
retries (`pipeline/_lake.py`). Swap stays open as the excess valve: the
fence bounds what the build takes from RAM, the OS may page the rest.

Peak usage comes back for free (`memory.peak` / `PeakJobMemoryUsed`)
— observation only, no decision reads it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

from . import ram_ledger as _rl


@dataclass
class FenceResult:
    returncode: int
    stdout: str
    stderr: str
    capped: bool
    peak_gb: "float | None"
    fence_gb: "float | None"


def fence_gb_now(inflight: int = 1) -> "float | None":
    """The room this build may take: measured available minus the
    pressure line the rest of the framework already pauses at, split
    among the builds in flight (this one included). None = no room at
    all (the machine is already at or under the line) — the caller
    waits rather than launching into a zero fence."""
    room = _rl.available_gb() - _rl.pressure_low_gb(_rl.total_gb())
    if room <= 0:
        return None
    return room / max(1, int(inflight))


# ───────────────────────── Linux: transient user scope ─────────────────────────

# Runs INSIDE the scope after the command exits, so the cgroup files are
# still there to read: peak bytes, then the events (the `oom_kill`
# counter says whether the kernel stopped the build).
_LINUX_TRAILER = (
    'cg=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup); "$@"; rc=$?; '
    '{ cat "$cg/memory.peak"; cat "$cg/memory.events"; } '
    '> "$ASTERISM_FENCE_STATS" 2>/dev/null; exit $rc')


def linux_fenced_argv(args: "list[str]", *, fence_bytes: int,
                      stats_path: str) -> "list[str]":
    return ["systemd-run", "--user", "--scope", "--quiet",
            "-p", f"MemoryMax={int(fence_bytes)}", "--",
            "sh", "-c", _LINUX_TRAILER, "sh", *args]


def parse_linux_stats(text: str) -> "tuple[int | None, int]":
    """(`memory.peak` bytes or None, `oom_kill` count)."""
    peak: "int | None" = None
    kills = 0
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) == 1 and parts[0].isdigit() and peak is None:
            peak = int(parts[0])
        elif len(parts) == 2 and parts[0] == "oom_kill" and parts[1].isdigit():
            kills = int(parts[1])
    return peak, kills


def classify(*, rc: int, oom_kills: int, stats_seen: bool) -> bool:
    """Capped = the kernel's OOM killer fired inside the fence. When the
    trailer shell itself was the victim no stats exist; a SIGKILL exit
    with no stats is the remaining fingerprint."""
    if oom_kills > 0:
        return True
    if not stats_seen and rc in (137, -9):
        return True
    return False


_LINUX_PROBE: "bool | None" = None
_LINUX_PROBE_LOCK = threading.Lock()


def _linux_supported() -> bool:
    """One-time probe: a user scope with a memory limit must be creatable
    (systemd-run present, memory controller delegated to the user
    slice). A host that cannot fence runs builds unfenced and says so
    once — the pre-fence shape, not a silent downgrade."""
    global _LINUX_PROBE
    with _LINUX_PROBE_LOCK:
        if _LINUX_PROBE is not None:
            return _LINUX_PROBE
        ok = False
        if shutil.which("systemd-run"):
            try:
                r = subprocess.run(
                    ["systemd-run", "--user", "--scope", "--quiet",
                     "-p", "MemoryMax=1G", "--", "true"],
                    capture_output=True, text=True, timeout=30)
                ok = r.returncode == 0
                if not ok:
                    print(f"[fence] no user memory scope here — builds run "
                          f"unfenced ({(r.stderr or '').strip()[:160]})",
                          flush=True)
            except (OSError, subprocess.TimeoutExpired) as e:
                print(f"[fence] systemd-run probe failed — builds run "
                      f"unfenced ({e})", flush=True)
        else:
            print("[fence] systemd-run not found — builds run unfenced",
                  flush=True)
        _LINUX_PROBE = ok
        return ok


def _run_linux(args, fence_gb, *, cwd, env, timeout) -> FenceResult:
    fd, stats_path = tempfile.mkstemp(prefix="asterism-fence-", suffix=".stats")
    os.close(fd)
    env = {**(env or os.environ), "ASTERISM_FENCE_STATS": stats_path}
    argv = linux_fenced_argv(list(args), fence_bytes=int(fence_gb * 2**30),
                             stats_path=stats_path)
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace",
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # `systemd-run --scope` forks the command as its own child; the
        # new session makes the whole tree one process group to kill.
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()
        proc.wait()
        _unlink(stats_path)
        raise
    try:
        text = open(stats_path, encoding="utf-8").read()
        seen = True
    except OSError:
        text, seen = "", False
    _unlink(stats_path)
    peak, kills = parse_linux_stats(text)
    return FenceResult(
        returncode=proc.returncode, stdout=out or "", stderr=err or "",
        capped=classify(rc=proc.returncode, oom_kills=kills, stats_seen=seen),
        peak_gb=(peak / 2**30) if peak is not None else None,
        fence_gb=float(fence_gb))


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ───────────────────────── Windows: Job Object ─────────────────────────

_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JobObjectExtendedLimitInformation = 9
_JobObjectLimitViolationInformation = 34


def _win_structs():
    import ctypes
    from ctypes import wintypes
    from .process_group import _build_structs
    _EXT = _build_structs(ctypes, wintypes)

    class _VIOL(ctypes.Structure):
        _fields_ = [
            ("LimitFlags", wintypes.DWORD),
            ("ViolationLimitFlags", wintypes.DWORD),
            ("IoReadBytes", ctypes.c_ulonglong),
            ("IoReadBytesLimit", ctypes.c_ulonglong),
            ("IoWriteBytes", ctypes.c_ulonglong),
            ("IoWriteBytesLimit", ctypes.c_ulonglong),
            ("PerJobUserTime", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("JobMemory", ctypes.c_ulonglong),
            ("JobMemoryLimit", ctypes.c_ulonglong),
            ("RateControlTolerance", wintypes.DWORD),
            ("RateControlToleranceLimit", wintypes.DWORD),
        ]
    return ctypes, wintypes, _EXT, _VIOL


def _run_windows(args, fence_gb, *, cwd, env, timeout) -> FenceResult:
    from .process_group import no_window_creationflags
    ctypes, wintypes, _EXT, _VIOL = _win_structs()
    k32 = ctypes.windll.kernel32
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                            wintypes.LPVOID, wintypes.DWORD]
    k32.QueryInformationJobObject.restype = wintypes.BOOL
    k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                              wintypes.LPVOID, wintypes.DWORD,
                                              wintypes.LPVOID]
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.TerminateJobObject.restype = wintypes.BOOL
    k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]

    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise OSError("CreateJobObjectW failed")
    try:
        info = _EXT()
        info.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_JOB_MEMORY | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        info.JobMemoryLimit = int(fence_gb * 2**30)
        if not k32.SetInformationJobObject(
                job, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            raise OSError("SetInformationJobObject failed")
        proc = subprocess.Popen(
            list(args), cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", creationflags=no_window_creationflags())
        # A child joins its parent's job automatically; lake's lean
        # compiles therefore land inside this job. Assigned right after
        # spawn — lake reads its manifest before it forks anything.
        if not k32.AssignProcessToJobObject(job, wintypes.HANDLE(proc._handle)):
            err = ctypes.get_last_error()
            proc.kill()
            proc.wait()
            raise OSError(f"AssignProcessToJobObject failed ({err})")
        try:
            out, err_text = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            k32.TerminateJobObject(job, 137)
            proc.wait()
            raise
        viol = _VIOL()
        capped = False
        if k32.QueryInformationJobObject(
                job, _JobObjectLimitViolationInformation,
                ctypes.byref(viol), ctypes.sizeof(viol), None):
            capped = bool(viol.ViolationLimitFlags & _JOB_OBJECT_LIMIT_JOB_MEMORY)
        peak_gb = None
        if k32.QueryInformationJobObject(
                job, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info), None):
            peak_gb = info.PeakJobMemoryUsed / 2**30
        if not capped and proc.returncode != 0 and peak_gb is not None \
                and peak_gb >= fence_gb * 0.98:
            # the violation record can be missed when the last process
            # exits before the query; the peak pinned at the limit is the
            # same event
            capped = True
        return FenceResult(returncode=proc.returncode, stdout=out or "",
                           stderr=err_text or "", capped=capped,
                           peak_gb=peak_gb, fence_gb=float(fence_gb))
    finally:
        k32.CloseHandle(job)


# ───────────────────────── entry ─────────────────────────

def fence_supported() -> bool:
    if sys.platform == "win32":
        return True
    if sys.platform.startswith("linux"):
        return _linux_supported()
    return False


def run_fenced(args: "list[str]", fence_gb: float, *, cwd, env=None,
               timeout: float) -> FenceResult:
    """Run `args` under a memory fence of `fence_gb`. Raises
    `subprocess.TimeoutExpired` after killing the whole fenced tree. A
    host without a fence runs the command bare (fence_gb=None in the
    result, capped never True)."""
    if sys.platform == "win32":
        return _run_windows(args, fence_gb, cwd=cwd, env=env, timeout=timeout)
    if sys.platform.startswith("linux") and _linux_supported():
        return _run_linux(args, fence_gb, cwd=cwd, env=env, timeout=timeout)
    r = subprocess.run(list(args), cwd=cwd, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return FenceResult(returncode=r.returncode, stdout=r.stdout or "",
                       stderr=r.stderr or "", capped=False, peak_gb=None,
                       fence_gb=None)
