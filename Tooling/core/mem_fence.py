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

Two amendments from the first real fenced build (SP7, 2026-09-01 23:04Z:
a 1.23G fence around a 3.2G module while the operator's Chrome was open;
lean ran at 31% CPU, 1.79M major faults, paging into zram):

* THE FENCE FOLLOWS THE ROOM. Sizing happens at launch, but the room
  does not hold still — the operator closed Chrome, available rose to
  3.8G, and the fence stayed at 1.23G until a hand-typed
  `set-property` unblocked it. `grow_to` is polled while the build runs
  and the OS limit is raised in place. It only ever grows: shrinking
  would kill a build that is already inside its limit for a reading
  taken a second ago.
* THE WALL COUNTS CPU SECONDS. The 600s wall-clock wall would have
  failed that build — promotion rolled back, brick re-dispatched, half
  an hour of formalizer work lost — for being slow, which is what
  paging looks like. A build gets a budget of COMPUTE; wall-clock is
  only the loose net under a tree that never runs. This is the shape
  the elaboration wall took on 2026-08-29 (`lsp/gateway/wall.py`).
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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
    #: What the fence ENDED at — `fence_gb` plus every raise `grow_to`
    #: bought while the build ran.
    fence_final_gb: "float | None" = None
    #: CPU seconds of the whole fenced tree (the budget's meter), and
    #: the wall-clock it took. None when there was nothing to meter.
    cpu_sec: "float | None" = None
    wall_sec: "float | None" = None


#: Poll slice — how often the fenced tree's meters are read, the two
#: clocks checked and the fence re-sized. `gateway/wall.py` polls an
#: elaboration every 15s because only the verdict is time-critical
#: there; a build's fence must FOLLOW the room while the build runs, so
#: this one is a few seconds.
BUILD_POLL_SLICE_SEC = 2.0

#: Wall-clock cap = CPU budget × this. A COPY of
#: `lsp/gateway/wall.ELAB_WALL_CLOCK_FACTOR`, not an import: `core/`
#: must not depend on the gateway. `tests/test_mem_fence.py` pins the
#: two together so the copy cannot drift.
BUILD_WALL_CLOCK_FACTOR = 4.0

#: Smallest raise worth an OS call. The room reading moves by tens of
#: megabytes every poll; without a step the fence would spend a
#: `set-property` spawn per slice chasing noise.
FENCE_GROW_STEP_GB = 0.25


class FenceTimeout(subprocess.TimeoutExpired):
    """`subprocess.TimeoutExpired` that says WHICH clock fired — the CPU
    budget or the loose wall-clock net. Callers that only know the base
    class still catch it; `_lake` reads `.reason` into the build detail
    so the failure is not a bare number."""

    def __init__(self, cmd, timeout, reason: str):
        super().__init__(cmd, timeout)
        self.reason = str(reason)

    def __str__(self) -> str:
        return f"fenced command timed out — {self.reason}"


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


def next_fence_gb(current: float, want: "float | None") -> "float | None":
    """The fence to raise to, or None to leave it alone."""
    if want is None:
        return None
    want = float(want)
    if want < float(current) + FENCE_GROW_STEP_GB:
        return None
    return want


def decide(cpu_sec: "float | None", wall_sec: float, budget: float,
           clock_cap: float) -> "str | None":
    """Which clock, if either, has fired — the wall decision, pure.

    CPU seconds are the budget: a build that is merely slow because the
    machine is crowded or paging still got its compute, and failing it
    is the mistake of 2026-09-01. Wall-clock is only the net under a
    tree that never runs. With no CPU meter (an unfenced host) the
    budget is spent on wall-clock instead."""
    if cpu_sec is None:
        if wall_sec >= budget:
            return (f"{wall_sec:.0f}s wall-clock, no CPU meter "
                    f"(budget {budget:.0f}s)")
        return None
    if cpu_sec >= budget:
        return f"{cpu_sec:.0f} CPU-s of the {budget:.0f} CPU-s budget"
    if wall_sec >= clock_cap:
        return (f"wall-clock cap {clock_cap:.0f}s reached with only "
                f"{cpu_sec:.0f}s of CPU spent — starved or hung")
    return None


class _Pump:
    """Drains stdout/stderr in a thread so the poll loop can meter the
    tree without the pipes filling and deadlocking it."""

    def __init__(self, proc):
        self.stdout = ""
        self.stderr = ""
        self._t = threading.Thread(target=self._drain, args=(proc,),
                                   daemon=True)
        self._t.start()

    def _drain(self, proc) -> None:
        out, err = proc.communicate()
        self.stdout, self.stderr = out or "", err or ""

    def done(self, timeout: float) -> bool:
        self._t.join(timeout)
        return not self._t.is_alive()


def _await_fenced(pump: _Pump, *, cmd, meter, grow, cpu_budget_sec, kill
                  ) -> "tuple[float | None, float]":
    """Wait for the fenced tree, one poll slice at a time: read the CPU
    meter, check both clocks, let the fence follow the room. Returns
    `(cpu_sec, wall_sec)`; on the wall the whole tree is killed and
    `FenceTimeout` names the clock that fired."""
    budget = float(cpu_budget_sec)
    clock_cap = budget * BUILD_WALL_CLOCK_FACTOR
    t0 = time.monotonic()
    cpu: "float | None" = None
    while True:
        elapsed = time.monotonic() - t0
        slice_s = min(BUILD_POLL_SLICE_SEC, max(0.01, clock_cap - elapsed))
        if pump.done(slice_s):
            last = meter()
            return (last if last is not None else cpu), time.monotonic() - t0
        reading = meter()
        if reading is not None:
            cpu = reading
        reason = decide(cpu, time.monotonic() - t0, budget, clock_cap)
        if reason is not None:
            kill()
            pump.done(30.0)
            raise FenceTimeout(cmd, budget, reason)
        grow()


# ───────────────────────── Linux: transient user scope ─────────────────────────

# Runs INSIDE the scope after the command exits, so the cgroup files are
# still there to read: peak bytes, then the events (the `oom_kill`
# counter says whether the kernel stopped the build).
_LINUX_TRAILER = (
    'cg=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup); "$@"; rc=$?; '
    '{ cat "$cg/memory.peak"; cat "$cg/memory.events"; } '
    '> "$ASTERISM_FENCE_STATS" 2>/dev/null; exit $rc')


def linux_fenced_argv(args: "list[str]", *, fence_bytes: int,
                      stats_path: str, unit: "str | None" = None
                      ) -> "list[str]":
    """`--unit` names the scope so its limit can be raised in place
    later (`linux_set_property_argv`) and its cgroup found from outside
    it (`_linux_scope_cgroup`)."""
    return ["systemd-run", "--user", "--scope", "--quiet",
            *([f"--unit={unit}"] if unit else []),
            "-p", f"MemoryMax={int(fence_bytes)}", "--",
            "sh", "-c", _LINUX_TRAILER, "sh", *args]


def linux_set_property_argv(unit: str, fence_bytes: int) -> "list[str]":
    """Raise a live scope's memory limit — no sudo, verified by hand on
    the SP7 2026-09-02."""
    return ["systemctl", "--user", "set-property", unit,
            f"MemoryMax={int(fence_bytes)}"]


def parse_cpu_usage_sec(text: str) -> "float | None":
    """`cpu.stat`'s `usage_usec` (user+system of the whole cgroup), in
    seconds — the budget's meter on Linux."""
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "usage_usec":
            try:
                return int(parts[1]) / 1e6
            except ValueError:
                return None
    return None


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


def _run_quiet(argv: "list[str]") -> bool:
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _linux_scope_cgroup(unit: str) -> "str | None":
    """The scope's cgroup directory, resolved from OUTSIDE the scope so
    the poll loop can read its meters while the build runs."""
    try:
        r = subprocess.run(["systemctl", "--user", "show", unit,
                            "-p", "ControlGroup", "--value"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = (r.stdout or "").strip()
    if r.returncode != 0 or not path or path == "/":
        return None
    return "/sys/fs/cgroup" + path


def _run_linux(args, fence_gb, *, cwd, env, cpu_budget_sec,
               grow_to=None) -> FenceResult:
    fd, stats_path = tempfile.mkstemp(prefix="asterism-fence-", suffix=".stats")
    os.close(fd)
    unit = f"asterism-build-{secrets.token_hex(4)}.scope"
    env = {**(env or os.environ), "ASTERISM_FENCE_STATS": stats_path}
    argv = linux_fenced_argv(list(args), fence_bytes=int(fence_gb * 2**30),
                             stats_path=stats_path, unit=unit)
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace",
                            start_new_session=True)
    state = {"fence": float(fence_gb), "cg": None, "tries": 0, "peak": 0}

    def cgroup() -> "str | None":
        # the scope needs a moment to register; a host where it never
        # does is metered by wall-clock instead of spawning systemctl
        # every slice forever
        if state["cg"] is None and state["tries"] < 3:
            state["tries"] += 1
            state["cg"] = _linux_scope_cgroup(unit)
        return state["cg"]

    def meter() -> "float | None":
        cg = cgroup()
        if not cg:
            return None
        raw = _read_text(os.path.join(cg, "memory.peak")).strip()
        if raw.isdigit():
            state["peak"] = max(state["peak"], int(raw))
        return parse_cpu_usage_sec(_read_text(os.path.join(cg, "cpu.stat")))

    def grow() -> None:
        if grow_to is None:
            return
        try:
            want = next_fence_gb(state["fence"], grow_to())
        except Exception:  # noqa: BLE001 — a broken reading never fails a build
            return
        if want is None or not cgroup():
            return
        if _run_quiet(linux_set_property_argv(unit, int(want * 2**30))):
            state["fence"] = want
            print(f"[fence] {unit} raised to {want:.1f}G — the machine "
                  f"freed room while the build ran", flush=True)

    def kill() -> None:
        # `systemd-run --scope` forks the command as its own child; the
        # new session makes the whole tree one process group to kill.
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()

    pump = _Pump(proc)
    try:
        cpu_sec, wall_sec = _await_fenced(
            pump, cmd=argv, meter=meter, grow=grow,
            cpu_budget_sec=cpu_budget_sec, kill=kill)
    except FenceTimeout:
        proc.wait()
        _unlink(stats_path)
        raise
    proc.wait()
    text = _read_text(stats_path)
    seen = bool(text)
    _unlink(stats_path)
    peak, kills = parse_linux_stats(text)
    if peak is None and state["peak"]:
        peak = state["peak"]
    return FenceResult(
        returncode=proc.returncode, stdout=pump.stdout, stderr=pump.stderr,
        capped=classify(rc=proc.returncode, oom_kills=kills, stats_seen=seen),
        peak_gb=(peak / 2**30) if peak is not None else None,
        fence_gb=float(fence_gb), fence_final_gb=state["fence"],
        cpu_sec=cpu_sec, wall_sec=wall_sec)


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ───────────────────────── Windows: Job Object ─────────────────────────

_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JobObjectBasicAccountingInformation = 1
_JobObjectExtendedLimitInformation = 9
_JobObjectLimitViolationInformation = 34
_WIN_LIMIT_FLAGS = (_JOB_OBJECT_LIMIT_JOB_MEMORY
                    | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)


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

    class _ACCT(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", wintypes.LARGE_INTEGER),
            ("TotalKernelTime", wintypes.LARGE_INTEGER),
            ("ThisPeriodTotalUserTime", wintypes.LARGE_INTEGER),
            ("ThisPeriodTotalKernelTime", wintypes.LARGE_INTEGER),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]
    return ctypes, wintypes, _EXT, _VIOL, _ACCT


def _run_windows(args, fence_gb, *, cwd, env, cpu_budget_sec,
                 grow_to=None) -> FenceResult:
    from .process_group import no_window_creationflags
    ctypes, wintypes, _EXT, _VIOL, _ACCT = _win_structs()
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
    state = {"fence": float(fence_gb)}

    def set_limit(gb: float) -> bool:
        lim = _EXT()
        lim.BasicLimitInformation.LimitFlags = _WIN_LIMIT_FLAGS
        lim.JobMemoryLimit = int(gb * 2**30)
        return bool(k32.SetInformationJobObject(
            job, _JobObjectExtendedLimitInformation,
            ctypes.byref(lim), ctypes.sizeof(lim)))

    try:
        if not set_limit(state["fence"]):
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

        acct = _ACCT()

        def meter() -> "float | None":
            if k32.QueryInformationJobObject(
                    job, _JobObjectBasicAccountingInformation,
                    ctypes.byref(acct), ctypes.sizeof(acct), None):
                # 100-ns units, every process the job ever held
                return (acct.TotalUserTime + acct.TotalKernelTime) / 1e7
            return None

        def grow() -> None:
            if grow_to is None:
                return
            try:
                want = next_fence_gb(state["fence"], grow_to())
            except Exception:  # noqa: BLE001 — a broken reading never fails a build
                return
            if want is None:
                return
            if set_limit(want):
                state["fence"] = want
                print(f"[fence] job raised to {want:.1f}G — the machine "
                      f"freed room while the build ran", flush=True)

        pump = _Pump(proc)
        try:
            cpu_sec, wall_sec = _await_fenced(
                pump, cmd=list(args), meter=meter, grow=grow,
                cpu_budget_sec=cpu_budget_sec,
                kill=lambda: k32.TerminateJobObject(job, 137))
        except FenceTimeout:
            proc.wait()
            raise
        proc.wait()
        viol = _VIOL()
        capped = False
        if k32.QueryInformationJobObject(
                job, _JobObjectLimitViolationInformation,
                ctypes.byref(viol), ctypes.sizeof(viol), None):
            capped = bool(viol.ViolationLimitFlags & _JOB_OBJECT_LIMIT_JOB_MEMORY)
        peak_gb = None
        info = _EXT()
        if k32.QueryInformationJobObject(
                job, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info), None):
            peak_gb = info.PeakJobMemoryUsed / 2**30
        if not capped and proc.returncode != 0 and peak_gb is not None \
                and peak_gb >= state["fence"] * 0.98:
            # the violation record can be missed when the last process
            # exits before the query; the peak pinned at the limit is the
            # same event
            capped = True
        return FenceResult(returncode=proc.returncode, stdout=pump.stdout,
                           stderr=pump.stderr, capped=capped,
                           peak_gb=peak_gb, fence_gb=float(fence_gb),
                           fence_final_gb=state["fence"],
                           cpu_sec=cpu_sec, wall_sec=wall_sec)
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
               cpu_budget_sec: float, grow_to=None) -> FenceResult:
    """Run `args` under a memory fence of `fence_gb`.

    `cpu_budget_sec` is the budget in CPU SECONDS of the fenced tree,
    with a wall-clock net at `× BUILD_WALL_CLOCK_FACTOR`; exceeding
    either kills the whole tree and raises `FenceTimeout` (a
    `subprocess.TimeoutExpired`) naming the clock that fired. `grow_to`,
    when given, is polled every slice: a larger reading raises the OS
    limit in place, never lowers it. A host without a fence runs the
    command bare — no CPU meter there, so the budget is plain
    wall-clock (fence_gb=None in the result, capped never True)."""
    if sys.platform == "win32":
        return _run_windows(args, fence_gb, cwd=cwd, env=env,
                            cpu_budget_sec=cpu_budget_sec, grow_to=grow_to)
    if sys.platform.startswith("linux") and _linux_supported():
        return _run_linux(args, fence_gb, cwd=cwd, env=env,
                          cpu_budget_sec=cpu_budget_sec, grow_to=grow_to)
    t0 = time.monotonic()
    r = subprocess.run(list(args), cwd=cwd, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=cpu_budget_sec)
    return FenceResult(returncode=r.returncode, stdout=r.stdout or "",
                       stderr=r.stderr or "", capped=False, peak_gb=None,
                       fence_gb=None, fence_final_gb=None, cpu_sec=None,
                       wall_sec=time.monotonic() - t0)
