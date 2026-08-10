"""`compute` — a calculator for the agents, and nothing else.

WHAT IT IS FOR. The Adversary's job is to attack a proposed lemma, and
the sharpest attack is a small explicit counterexample: enumerate every
union-closed family on a 4-element ground set, sweep an inequality over
a parameter range, check an algebraic identity numerically. 33k shell
calls were surveyed to size this (2026-08-10); ~3% were exactly that,
and it is the only part of the shell with no substitute.

WHAT IT PROVES: NOTHING. A Python computation is not a proof, whatever
it prints and whichever direction the result points. The only thing in
this framework that establishes a mathematical claim is the Lean kernel.
Owner ruling 2026-08-10, and it is stated this bluntly on purpose — an
earlier draft said only "a clean sweep is not evidence, a counterexample
is", which leaves the agent deciding which of its results count. It
does not decide. `RESULT_HEADER` is prepended to every output so the
statement travels WITH the data: a downstream agent reads the artifact,
not the tool description.

HOW IT IS CONTAINED, in the order that matters:

  1. A separate interpreter. The sandbox venv has numpy and does NOT
     have this framework installed, so `import Tooling` — the SQLite
     layer holding the whole run — raises ModuleNotFoundError. This is
     the load-bearing control, and it is a fact you can test rather than
     a flag whose semantics can surprise you: stripping `PYTHONPATH`
     does NOT work (the editable install registers a `.pth` in
     site-packages), and neither does `-I` (it implies `-E -s`, not
     `-S`). Both measured 2026-08-10; `-S` does block it, but also
     removes numpy, since both arrive through site-packages.
  2. An allowlisted environment with no PATH — so a `subprocess` that
     got past the hook has nothing to find — and no provider secrets.
  3. `launcher.py`'s audit hook (PEP 578), installed before the agent's
     first byte and self-tested. Refuses filesystem, network and shell
     with a message naming the tool to use instead.
  4. A memory cap and a WALL-CLOCK timeout enforced from out here. The
     wall clock is deliberately not the Job Object's own time limit,
     which counts user-mode CPU: `time.sleep` and blocked I/O accrue
     almost none and would sail past it.

Enforcement strength is NOT the same on all three platforms and the
declaration says so rather than implying parity (same discipline as
`llm/capabilities.enforcement_strength`):

  Windows  Job Object, per-process commit cap + ActiveProcessLimit=1.
           Hard: the allocation fails inside the child.
  Linux    RLIMIT_AS. Hard.
  macOS    RLIMIT_AS is widely ignored there, so the cap degrades to the
           watchdog POLLING RSS. Soft: a fast allocator can overshoot
           between samples. UNVERIFIED from this workstation — no mac to
           measure on; carried as an advisory claim, not a measurement.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import provision

#: Wall clock. FRAMEWORK-SET and absent from the tool signature — the
#: agent cannot see or raise it (owner ruling 2026-08-10). A calculator
#: that needs more than this is not doing arithmetic, it is searching,
#: and a search that big belongs in a designed experiment.
TIMEOUT_SEC = 30
#: Toy scale by construction: the measured workload's biggest job is
#: 2**16 candidate families.
MEMORY_MB = 256
#: Output ceiling. The agent pays for every byte in its next turn.
MAX_OUTPUT_CHARS = 8000
#: Sampling period for the soft (macOS) memory cap.
_RSS_POLL_SEC = 0.25
#: OS-level ceiling on processes inside the job. Two, not one: a Windows
#: venv's `python.exe` is a REDIRECTOR that launches the base
#: interpreter, so a limit of 1 refuses the sandbox's own startup
#: ("Unable to create process using …", measured 2026-08-10 — the first
#: run of the whole matrix failed identically on every case). So this is
#: a BACKSTOP that bounds *extra* processes at one, not at zero; the
#: control that actually stops a shell is the audit hook plus an
#: environment with no PATH.
_MAX_PROCESSES = 2

RESULT_HEADER = (
    "[compute] Python output. NOT a proof: no computation here "
    "establishes a mathematical claim, in either direction — only the "
    "Lean kernel does. Use this to find counterexamples and to check "
    "your own arithmetic.\n"
)


@dataclass(frozen=True)
class ComputeResult:
    rc: int
    output: str
    seconds: float
    killed: str = ""          # "timeout" | "memory" | ""

    def render(self) -> str:
        body = self.output
        if len(body) > MAX_OUTPUT_CHARS:
            dropped = len(body) - MAX_OUTPUT_CHARS
            body = (body[:MAX_OUTPUT_CHARS]
                    + f"\n… {dropped} more characters dropped. Print less, "
                      f"or summarise inside the code.")
        if self.killed == "timeout":
            body += (f"\n[compute] stopped at the {TIMEOUT_SEC}s limit. "
                     f"Shrink the search — the limit is fixed.")
        elif self.killed == "memory":
            body += (f"\n[compute] stopped at the {MEMORY_MB} MB limit. "
                     f"Enumerate in batches instead of materialising "
                     f"everything.")
        return RESULT_HEADER + body


def _sandbox_env() -> "dict[str, str]":
    """Allowlist, never a strip. Empty but for what the interpreter
    itself needs to start: no PATH (so a shell has nothing to find), no
    provider credentials, nothing that identifies the host session."""
    env: "dict[str, str]" = {}
    for key in ("SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP",
                "LANG", "LC_ALL"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Single-threaded BLAS. Not a preference — numpy's OpenBLAS reserves
    # per-core thread buffers AT IMPORT, which blew the whole memory cap
    # before a line of agent code ran (measured 2026-08-10: every case in
    # the matrix died with "OpenBLAS error: Memory allocation still
    # failed"). A calculator has no use for parallel BLAS, and one thread
    # also makes the wall clock mean something.
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[var] = "1"
    return env


def _preexec():  # pragma: no cover — POSIX only
    """New session (so the whole tree dies with one killpg) plus a hard
    address-space cap where the OS honours one."""
    os.setsid()
    try:
        import resource
        cap = MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    except Exception:  # noqa: BLE001 — macOS ignores it; watchdog covers
        pass


def _kill(proc: subprocess.Popen, job) -> None:
    if job is not None:
        from ..core.process_group import terminate_job
        terminate_job(job)
        return
    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(proc.pid), 9)
        else:
            proc.kill()
    except Exception:  # noqa: BLE001
        pass


def _rss_mb(pid: int) -> float:
    try:
        import psutil
        return psutil.Process(pid).memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 — no psutil / process gone
        return 0.0


def run(code: str) -> ComputeResult:
    """Run `code` in the sandbox and return what it printed."""
    ready, why = provision.ensure_ready()
    if not ready:
        return ComputeResult(rc=127, output=f"[compute] unavailable: {why}",
                             seconds=0.0)

    workdir = tempfile.mkdtemp(prefix="asterism_compute_")
    launcher = str(Path(__file__).resolve().parent / "launcher.py")
    cmd = [str(provision.sandbox_python()), "-B", "-E", launcher, workdir]

    job = None
    popen_kw: dict = {}
    if sys.platform == "win32":
        from ..core.process_group import (assign_to_job, create_capped_job,
                                          no_window_creationflags)
        job = create_capped_job(MEMORY_MB, max_processes=_MAX_PROCESSES)
        popen_kw["creationflags"] = no_window_creationflags()
    else:
        popen_kw["preexec_fn"] = _preexec

    t0 = time.monotonic()
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", cwd=workdir, env=_sandbox_env(), **popen_kw)
    if job is not None:
        assign_to_job(job, proc)

    chunks: "list[str]" = []
    killed = ""

    def _drain() -> None:
        # Bounded reader on its own thread: a child that writes more than
        # we ever read fills the pipe buffer and DEADLOCKS rather than
        # being truncated.
        seen = 0
        assert proc.stdout is not None
        for line in proc.stdout:
            if seen < MAX_OUTPUT_CHARS * 4:
                chunks.append(line)
                seen += len(line)

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()
    try:
        proc.stdin.write(code)          # type: ignore[union-attr]
        proc.stdin.close()              # type: ignore[union-attr]
    except OSError:
        pass

    while proc.poll() is None:
        elapsed = time.monotonic() - t0
        if elapsed > TIMEOUT_SEC:
            killed = "timeout"
            break
        # Soft cap for the platform that ignores the hard one.
        if sys.platform == "darwin" and _rss_mb(proc.pid) > MEMORY_MB:
            killed = "memory"
            break
        time.sleep(_RSS_POLL_SEC)
    if killed:
        _kill(proc, job)
    proc.wait()
    reader.join(timeout=2)
    if job is not None:
        from ..core.process_group import terminate_job
        terminate_job(job)

    rc = proc.returncode or 0
    out = "".join(chunks).strip()
    if not out and not killed:
        out = "(no output — the code printed nothing)"
    # A Windows commit-limit kill surfaces as a MemoryError inside the
    # child, which is the honest message; only name it ourselves when we
    # were the one who pulled the trigger.
    return ComputeResult(rc=rc, output=out,
                         seconds=time.monotonic() - t0, killed=killed)
