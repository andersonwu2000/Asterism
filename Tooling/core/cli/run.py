"""Daemon/run lifecycle: `asterism run`, `asterism daemon start|stop|status`,
`asterism serve` — the log-tee'd dispatcher launch, the detached-daemon
singleton-lock lifecycle, and the localhost web UI process. Split out of
`Tooling/core/cli.py` (task A3, move-only) into the `core/cli/` package;
`Tooling/core/cli/__init__.py` re-exports this module's public (and
tested private) surface."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .. import dispatcher, fsutil
from ...state import db


# Daemon log lifecycle.
LOG_DIR = Path(".asterism") / "logs"
LOG_RETENTION_KEEP = 20  # most-recent N logs kept; older deleted on startup


class _Tee:
    """Write to multiple text streams. Used so the daemon's stdout
    appears on the operator's terminal AND in the per-run log file."""
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            # Per-stream resilience: a write failure on one stream (e.g. a
            # legacy cp950 console choking on a char outside its range)
            # must not kill the daemon nor starve the other streams (the
            # UTF-8 log file is the canonical forensic artifact). Belt to
            # `_force_utf8_io`'s reconfigure suspenders.
            try:
                st.write(s)
                st.flush()
            except (UnicodeEncodeError, OSError, ValueError):
                pass
        return len(s)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except (OSError, ValueError):
                pass

    def isatty(self):
        # Some downstream tools query isatty; report based on the
        # primary (terminal) stream.
        return getattr(self._streams[0], "isatty", lambda: False)()


def _log_filename(workspace: Path) -> str:
    """`<problem>_<UTC ts>.log` — `<problem>` falls back to `daemon`
    when the DB has no problems yet (e.g. first run before init), or
    `multi` when more than one problem is registered.

    No model in the name any more. It used to carry one, resolved from
    `builder` + `backward` — two keys the v33 Formalizer merge retired,
    so both fell through to DEFAULT_MODEL and the label named a model
    that had nothing to do with the run: 2026-08-06's log is
    `multi_claude-sonnet-4-6_…` for a run whose formalizer was
    gemini-3.6-flash-high and whose strategist was claude-opus-5. That
    is worse than no label, because the run's timing analyses are
    identified BY these filenames.

    A single token cannot honestly name a run with one model per seat,
    so the seats go where they fit: `seat_banner()` writes the whole
    table into the log's first lines, where it is accurate by
    construction and stays accurate when a seat moves mid-run.
    """
    problem = "daemon"
    try:
        conn = db.connect()
        names = [r[0] for r in conn.execute(
            "SELECT name FROM problems ORDER BY name").fetchall()]
        conn.close()
        if len(names) == 1:
            problem = names[0]
        elif len(names) > 1:
            problem = "multi"
    except Exception:
        # DB missing / unreadable: keep 'daemon' default
        pass
    return f"{problem}_{_utc_log_stamp()}.log"


def seat_banner() -> str:
    """The run's actual seats, for the head of its log.

    What the filename cannot say: one line per pipeline that spawns a
    model, with the provider and model it is configured to use right
    now. This is what a later timing or A/B analysis needs to know it is
    comparing like with like — and reading it off a filename is how a
    run gets attributed to a model it never used.
    """
    from .. import dispatcher
    try:
        seats = dispatcher._pipeline_seats()
    except Exception:  # noqa: BLE001 — a banner must never block a run
        return "[seats] unavailable"
    return "\n".join(
        [f"[seats] {kind}: {prov}/{model or '(provider default)'}"
         for kind, (prov, model) in sorted(seats.items())])


def _utc_log_stamp() -> str:
    """UTC timestamp for log filenames, `Z`-suffixed. Local-time names
    beside UTC DB timestamps mis-billed a 5h15m outage as 14.7 min
    (2026-07-19) — one clock, self-documented."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "Z"


def _open_run_log(workspace: Path) -> Path:
    """Ensure `.asterism/logs/` exists, prune oldest beyond retention,
    and return the new log file's path. Caller is responsible for
    actually opening + redirecting."""
    log_dir = workspace / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    _retain_recent_logs(log_dir, keep=LOG_RETENTION_KEEP)
    return log_dir / _log_filename(workspace)


def _retain_recent_logs(log_dir: Path, *, keep: int) -> list[Path]:
    """Delete .log files beyond the most-recent `keep` count
    (sorted by mtime). Returns the deleted paths for tests."""
    if not log_dir.exists():
        return []
    logs = sorted(log_dir.glob("*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    deleted: list[Path] = []
    for old in logs[keep:]:
        try:
            old.unlink()
            deleted.append(old)
        except OSError:
            pass
    return deleted


def _hard_exit_after_fatal(rc: int) -> None:
    """ZOMBIE-LOCK seam: after a dispatcher FATAL, `os._exit` is the only
    way to actually die — the pool's non-daemon worker threads (blocked on
    claude subprocesses) otherwise keep the process alive holding the
    daemon.pid lock, with no main loop left to cascade their results
    (sphere daemon #3, 2026-07-05). Module-level so tests can stub it and
    observe the re-raise instead of losing the test runner."""
    os._exit(rc)


def cmd_run(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    from .. import config as _cfg
    _cfg_err = _cfg.load_error(workspace)
    if _cfg_err:
        print(f"[cli] REFUSING to run: config unparseable — running on "
              f"defaults would evaporate the run's settings: {_cfg_err}",
              flush=True)
        return 1
    # Scope safety gate: a no-`--scope` run is workspace-wide — it
    # dispatches AND runs the recovery orphan-sweep across EVERY problem.
    # That is rarely intended and high-blast-radius (a stokes-scoped
    # restart once swept 148 committed proof files from other problems
    # before `--scope` was honored). The daemon is non-interactive, so the
    # guard refuses to start rather than prompt: require an explicit
    # `--all-problems` to confirm the rare workspace-wide intent.
    if getattr(args, "scope", None) is None and not getattr(
            args, "all_problems", False):
        print(
            "[cli] REFUSING to run without --scope: a no-scope run is "
            "WORKSPACE-WIDE (dispatch + orphan-sweep across every "
            "problem) and is rarely intended.\n"
            "      Re-run with --scope <problem> (e.g. "
            "--scope Geometry.stokes_theorem),\n"
            "      or pass --all-problems to confirm a deliberate "
            "workspace-wide run.",
            flush=True)
        return 2
    # Auto-tee daemon stdout/stderr into .asterism/logs/<...>.log so
    # post-run forensics + post-compact handoffs always have a canonical
    # artifact, while the operator still sees real-time output on the
    # terminal.
    log_path = _open_run_log(workspace)
    log_file = log_path.open("w", encoding="utf-8")
    print(f"[cli] log → {log_path.relative_to(workspace).as_posix()}",
          flush=True)
    # SSE tail pointer: the web UI follows daemon-current.txt. EVERY run
    # path must update it — when only daemon_start (the UI button) did,
    # a terminal-started run left the web log tail silently replaying
    # the previous run's file.
    try:
        (workspace / LOG_DIR / "daemon-current.txt").write_text(
            str(log_path), encoding="utf-8")
    except OSError:
        pass
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = _Tee(orig_stdout, log_file)
    sys.stderr = _Tee(orig_stderr, log_file)
    # The seat table goes in FIRST, before any dispatch line: what the
    # filename used to claim (and got wrong) now lives where it can be
    # true — one line per pipeline, with the model it actually runs.
    print(seat_banner(), flush=True)
    # Provider drift guard (background, non-fatal): does each seated
    # CLI still answer the way its capability entry says it does? Every
    # quota / misconfig detector we own is a substring match against
    # vendor prose, so a wording change at the SAME version is silent
    # until a run gets nowhere. Off the startup path because the probes
    # are CLI cold starts and nothing about dispatch waits on them.
    from ...llm import drift_guard as _drift_guard
    _drift_guard.start_background(workspace)
    try:
        rc = dispatcher.run(
            workspace,
            once=getattr(args, "once", False),
            scope=getattr(args, "scope", None),
        )
        _write_exit_summary(workspace, rc=rc, error=None,
                            scope=getattr(args, "scope", None))
        return rc
    except Exception as exc:
        _write_exit_summary(
            workspace, rc=2,
            error=f"{type(exc).__name__}: {exc}"[:400],
            scope=getattr(args, "scope", None))
        # Log the crash traceback HERE, while `sys.stderr` is still tee'd to
        # the log file and the file is still open. The `finally` below restores
        # `sys.stderr` and closes the log BEFORE an unhandled exception would
        # otherwise reach the interpreter's default handler — so without this
        # `except`, a `dispatcher.run` crash leaves `.asterism/logs/multi_*.log`
        # ending mid-tick with no traceback, making the daemon's self-
        # termination invisible (exactly what hid the green_theorem crash:
        # the log stopped cleanly at a `[dispatch] …` line). `print_exc`
        # writes to the tee'd `sys.stderr`, so the traceback lands in the log.
        print("[dispatcher] FATAL: unhandled exception — daemon exiting:",
              flush=True)
        traceback.print_exc()
        # ZOMBIE-LOCK guard (`_hard_exit_after_fatal` seam below;
        # sphere daemon #3, 2026-07-05): re-raising kills
        # only the MAIN thread — the pool's non-daemon worker threads (each
        # blocked on a claude subprocess for up to ~16min) keep the PROCESS
        # alive, still holding the daemon.pid lock and blocking every
        # restart, while no main loop exists to cascade their results. Kill
        # the registered in-flight subprocesses (same machinery as the
        # breaker exits) and hard-exit: the work is unrecoverable either
        # way, and the v17 lease sweep + startup recovery reclaim it.
        try:
            from ...llm import claude_cli as _ccli
            n = _ccli.request_shutdown()
            if n:
                print(f"[dispatcher] killed {n} in-flight agent "
                      f"subprocess(es) before FATAL exit", flush=True)
        except Exception:  # noqa: BLE001 — never mask the original crash
            pass
        sys.stdout, sys.stderr = orig_stdout, orig_stderr
        try:
            log_file.close()
        except OSError:
            pass
        _hard_exit_after_fatal(2)   # production: never returns
        raise                       # tests stub the seam → crash propagates
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        try:
            log_file.close()
        except OSError:
            pass


def _write_exit_summary(workspace: Path, *, rc: "int | None",
                        error: "str | None",
                        scope: "str | None" = None) -> None:
    """Record how the last run ended (read by `daemon_status` when
    idle) — a crashed run must not be indistinguishable from a finished
    one (both used to read 'Idle'). `scope` pins the ending to the
    problem it happened on, so its cockpit can surface the crash."""
    try:
        p = workspace / LOG_DIR / "daemon-exit.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"at": db.now(), "rc": rc, "error": error, "scope": scope}),
            encoding="utf-8")
    except OSError:
        pass


def _read_exit_summary(workspace: Path) -> "dict | None":
    try:
        raw = (workspace / LOG_DIR / "daemon-exit.txt").read_text(
            encoding="utf-8")
        d = json.loads(raw)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# Serializes check-then-spawn within one process (the serve API handles
# two Run clicks on two threads); the cross-process guard is the
# daemon-starting marker + the child's singleton lock.
_daemon_start_lock = threading.Lock()


def _daemon_live_pid(workspace: Path) -> "int | None":
    """Singleton-lock liveness: the daemon's pid iff the lock file names
    a live daemon instance (pid + start-time identity, the same
    reuse-proof check the lock itself uses)."""
    from .. import dispatcher as _disp
    pid_file = workspace / ".asterism" / "daemon.pid"
    try:
        lines = pid_file.read_text(encoding="utf-8").splitlines()
        pid = int(lines[0].strip())
        start = float(lines[1].strip()) if len(lines) > 1 else None
    except (OSError, ValueError, IndexError):
        return None
    return pid if _disp._lock_held_by_live_daemon(pid, start) else None


def _daemon_counts(workspace: Path) -> "tuple[int | None, int | None]":
    """(running pipelines, leased queue rows); (None, None) when the
    on-disk schema is BEHIND this code — SchemaBehind, a read-only consumer
    may not migrate, so there is nothing to count (2026-09-02: it fell
    into the blanket handler and printed `in_flight: -1`, which reads
    as a measurement rather than as "I could not look").

    2026-08-31: the old single number counted LEASED QUEUE ROWS and was
    displayed as "agents" — a stop-window read said 34 while 9 pipelines
    ran. `in_flight` now means running pipelines (what a human calls
    agents); the lease count stays as a separate diagnostic."""
    path = workspace / "asterism.db"
    if not path.exists():
        return 0, 0
    try:
        # Read-only on purpose: db.connect() CREATES a missing file (a
        # write), and this runs from the serve API's status poll too.
        conn = db.connect_readonly(path)
        # ONE statement: the pair describes one instant, not two reads.
        running, leases = conn.execute(
            "SELECT (SELECT count(*) FROM pipelines"
            "         WHERE finished_at IS NULL),"
            "       (SELECT count(*) FROM queue"
            "         WHERE owner_pid IS NOT NULL)").fetchone()
        conn.close()
        return int(running), int(leases)
    except db.SchemaBehind:
        return None, None
    except Exception:  # noqa: BLE001 — status must not crash
        return -1, -1


def daemon_status(workspace: Path) -> dict:
    """Daemon lifecycle status dict (shared by `asterism daemon status`
    and the serve API — one implementation, two surfaces)."""
    import time as _time
    from .. import dispatcher as _disp
    pid = _daemon_live_pid(workspace)
    # Boot window: daemon_start has returned but the child hasn't claimed
    # the singleton lock yet (heavy imports — seconds). The start side
    # already covers this gap with the anti-double-spawn marker; the
    # STATUS side must read the same marker or it reports "idle" and the
    # UI's Run button flashes back mid-start (owner, 2026-07-12). The
    # child consumes the marker right after claiming the lock, so
    # starting → running is seamless; a crashed boot ages out at 60s
    # (the marker's own staleness rule).
    starting = False
    if pid is None:
        try:
            marker = workspace / ".asterism" / "daemon-starting.txt"
            starting = _time.time() - marker.stat().st_mtime < 60
        except OSError:
            starting = False
    scope: str | None = None
    started_at: str | None = None
    if pid is not None or starting:
        # written by daemon_start; "" = workspace-wide (--all-problems)
        scope_file = workspace / ".asterism" / "logs" / "daemon-scope.txt"
        try:
            scope = scope_file.read_text(encoding="utf-8").strip() or None
        except OSError:
            scope = None
    if pid is not None:
        # pid-file line 2 is the daemon's process start time (the same
        # identity the singleton lock checks) — that IS this run's start.
        try:
            lines = (workspace / ".asterism" / "daemon.pid").read_text(
                encoding="utf-8").splitlines()
            started_at = datetime.fromtimestamp(
                float(lines[1].strip()), timezone.utc).isoformat()
        except (OSError, ValueError, IndexError):
            started_at = None
    code_stale = False
    if pid is not None:
        # the daemon writes its code fingerprint at boot; a mismatch
        # against the CURRENT tree means it runs old code. Transient by
        # design — the daemon's own drift watchdog drains and hands off
        # — but the status must say so while it lasts.
        try:
            born_fp = (workspace / ".asterism" / "logs" /
                       "daemon-fp.txt").read_text(encoding="utf-8").strip()
            if born_fp:
                from ...lsp.lifecycle import code_fingerprint
                code_stale = born_fp != code_fingerprint()
        except OSError:
            code_stale = False
    gw_phase, gw_slots = _gateway_status_once(workspace)
    from .. import degraded as _degraded
    from ...pipeline import _olean_warm as _promotion
    # ONE read: the two numbers come from the same connection, so the
    # pair describes one instant — and the serve status poll pays for
    # one read-only open rather than two.
    _running, _leases = _daemon_counts(workspace)
    return {
        "running": pid is not None,
        # the boot window between daemon_start and the child's lock claim
        "starting": starting,
        "pid": pid,
        "scope": scope,
        "started_at": started_at,
        "code_stale": code_stale,
        # a stop-file left behind by a dead daemon is residue, not a
        # state — "stopping" is only meaningful while something runs
        "stopping": pid is not None
        and _disp.stop_file_path(workspace).exists(),
        # `in_flight` = running pipelines (the "agents" number);
        # `in_flight_leases` = leased queue rows (diagnostic); both null
        # when `schema` is "behind" — nothing could be counted.
        "in_flight": _running,
        "in_flight_leases": _leases,
        # "behind" = the on-disk schema is older than this code, so the status
        # is reading a DB it may not open; run the engine once to migrate
        "schema": "ok" if _running is not None else "behind",
        # silent-degradation ledger (core/degraded.py): best-effort steps
        # that failed and logged one line — dedupe pre-flight / probe
        # refusals etc. Per run (reset at daemon boot); {} = nothing
        # degraded. The patrol reads this instead of grepping logs.
        "degraded": _degraded.snapshot(workspace),
        # promotion cold builds in flight (pipeline/_olean_warm.py). The
        # gate is a background thread, not a pipeline, so `in_flight`
        # says 0 while it holds the machine for ten minutes — the
        # operator read that as "nobody on the field" (2026-09-01).
        "promotion_builds": _promotion.inflight_builds(workspace),
        # gateway phase ('warming'/'ready'/None): the first minutes of
        # a cold run are Lean warm-up — without this the user stares
        # at dead air (Test.Test3 run, 2026-07-07)
        "gateway": gw_phase,
        # Lean-field capacity (frontend ask 2026-08-25): {target, open,
        # free} from the same single /health round-trip as the phase —
        # the old phase/slots pair re-asked the same URL back to back,
        # doubling status load on a queue that was already drowning
        # (frontend finding, flagship 2026-08-27). None while no gateway.
        "slots": gw_slots,
        # how the LAST run ended ({at, rc, error, scope}) — only
        # meaningful while idle; tells "finished" from "crashed", and a
        # BOOTING run's page must not resurface the previous ending
        "last_exit": None if (pid is not None or starting)
        else _read_exit_summary(workspace),
    }


def _gateway_status_once(workspace: Path) -> "tuple[str | None, dict | None]":
    """(phase, slots) from AT MOST ONE /health round-trip. The old
    helper pair asked the same URL twice per status poll (phase, then
    slots) — pure double load, and on the saturated flagship it fed the
    very accept backlog the status was trying to observe (frontend
    finding, 2026-08-27).

    The socket is asked only once a gateway has SAID it is there
    (`gateway_live_pid` — the process's own presence marker). Dialling
    unconditionally cost a full connect timeout whenever no gateway was
    up: a connect to a dead local port is not refused on Windows, it
    hangs, and this rides every status poll of every console screen —
    1.016s of a 1.02s `/api/daemon` (measured 2026-09-03). Absence is a
    structured signal now, not something to prove with a socket."""
    import json as _json
    import urllib.request
    try:
        from ...lsp.lifecycle import gateway_live_pid
        present = gateway_live_pid(workspace) is not None
    except Exception:  # noqa: BLE001 — status must not crash
        present = False
    if not present:
        return None, None
    h = None
    try:
        from ...lsp.lifecycle import _gateway_port
        req = urllib.request.Request(
            f"http://127.0.0.1:{_gateway_port(workspace)}/health")
        with urllib.request.urlopen(req, timeout=1.0) as r:
            h = _json.loads(r.read())
    except Exception:  # noqa: BLE001 — status must not crash
        h = None
    if h is not None and h.get("backend_ready"):
        return "ready", {"target": h.get("warm_target"),
                         "open": h.get("workers_open"),
                         "free": h.get("workers_free")}
    try:
        from ...lsp.lifecycle import warming_pid
        phase = "warming" if warming_pid(workspace) is not None else None
    except Exception:  # noqa: BLE001 — status must not crash
        phase = None
    return phase, None


def daemon_start(workspace: Path, *, scope: "str | None" = None,
                 once: bool = False,
                 wait_lock_sec: float = 0.0) -> "tuple[int, str]":
    """Detached daemon start. Returns (exit_code, message). Refuses (1)
    while a daemon holds the singleton lock; on success writes the
    per-run log + the daemon-current.txt pointer the SSE tail follows.

    `wait_lock_sec` > 0 retries the refusal for that long — the code-
    drift HANDOFF relay uses it: the dying daemon spawns this waiter
    BEFORE releasing its own lock, and the waiter's start lands the
    moment the lock frees."""
    import subprocess
    import time as _time
    from .. import config as _cfg
    from .. import dispatcher as _disp
    # B4 (2026-07-24): a present-but-unparseable config must refuse the
    # start — silently running on defaults evaporates the run's settings.
    _cfg_err = _cfg.load_error(workspace)
    if _cfg_err:
        return 1, (f"config unparseable — refusing to start on defaults: "
                   f"{_cfg_err}. Fix Asterism.yaml (or the python env) "
                   "and retry.")
    # #158: a scope matching no registered problem can never dispatch —
    # the daemon would boot and idle forever, indistinguishable from
    # health (08-04 SLC: `reset` deletes the problems row; two restarts
    # idled ~20min before the missing `init` was noticed). Refuse here,
    # in the caller's face; dispatcher.run re-checks for direct `run`
    # invocations and the code-drift handoff successor.
    if scope:
        _mismatch = _disp.scope_mismatch_reason(workspace, scope)
        if _mismatch:
            return 1, _mismatch
    deadline = _time.time() + wait_lock_sec
    while True:
        refusal: "str | None" = None
        with _daemon_start_lock:
            pid = _daemon_live_pid(workspace)
            if pid is not None:
                refusal = (f"REFUSED: a daemon is already running (pid {pid})"
                           f" — one daemon per workspace (singleton lock)")
            else:
                # Anti-double-spawn window: the child takes seconds to boot
                # and claim the singleton lock; two near-simultaneous starts
                # both passed the check above and both spawned (the loser
                # died silently AFTER this call returned "started", and
                # last-writer scope made the UI lie about what runs). The
                # marker covers the boot gap; the child consumes it once
                # the lock is settled.
                marker = workspace / ".asterism" / "daemon-starting.txt"
                try:
                    if _time.time() - marker.stat().st_mtime < 60:
                        refusal = ("REFUSED: a daemon is already starting "
                                   "(another Run landed moments ago) — give "
                                   "it a few seconds, then check status")
                except OSError:
                    pass
                if refusal is None:
                    # Tolerant unlinks: the serve status poll reads these
                    # files every ~2s; a collision raised WinError 32 and
                    # killed the drift-handoff waiter (2026-07-13 21:01,
                    # convicted 07-14 via handoff-waiter.log).
                    fsutil.unlink_tolerant(_disp.stop_file_path(workspace))
                    logs = workspace / ".asterism" / "logs"
                    logs.mkdir(parents=True, exist_ok=True)
                    marker.write_text(db.now(), encoding="utf-8")
                    # last run's exit summary belongs to the last run — a
                    # force-killed run writes none, and a stale one must not
                    # be reported as this run's ending
                    fsutil.unlink_tolerant(logs / "daemon-exit.txt")
        if refusal is None:
            break
        if _time.time() >= deadline:
            return 1, refusal
        _time.sleep(1.0)
    log_path = logs / f"daemon_{_utc_log_stamp()}.log"
    argv = [sys.executable, "-m", "Tooling.core.cli", "run"]
    if once:
        argv.append("--once")
    if scope:
        argv += ["--scope", scope]
    else:
        argv.append("--all-problems")
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    daemon_pid: "int | str" = "?"
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        base_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        # The daemon must NOT be the caller's child: taskkill /T on the
        # serve process (or any UI host) walks the LIVE parent-child
        # chain and would reap the daemon and every in-flight prover
        # with it (2026-07-10 incident — a serve restart killed the
        # putnam marathon). A relay spawns the daemon and exits at
        # once, so the daemon is reparented and the chain is broken.
        # The daemon still binds ITSELF to its own kill-on-close Job
        # Object at boot (dispatcher.run) — orphan-prover protection is
        # untouched. The relay also breaks away from the CALLER's job
        # when that job permits it (a handoff relay spawned by a dying
        # daemon must escape ITS kill-on-close job or die with it).
        from .. import process_group
        relay_src = (
            "import subprocess, sys\n"
            "flags = 0x00000008 | 0x00000200\n"
            "log = open(sys.argv[2], 'ab')\n"
            "p = subprocess.Popen(sys.argv[3:], cwd=sys.argv[1],\n"
            "                     stdout=log, stderr=subprocess.STDOUT,\n"
            "                     stdin=subprocess.DEVNULL,\n"
            "                     creationflags=flags)\n"
            "print(p.pid, flush=True)\n"
        )
        relay = subprocess.Popen(
            [sys.executable, "-c", relay_src, str(workspace),
             str(log_path), *argv],
            cwd=str(workspace), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=base_flags | process_group.breakaway_creationflags(),
            env=env)
        try:
            out, _ = relay.communicate(timeout=30)
            daemon_pid = int(out.strip())
        except (ValueError, subprocess.TimeoutExpired):
            daemon_pid = "?"  # relay hiccup — the singleton lock is truth
    else:
        # POSIX has no tree-kill footgun (killing serve never reaps
        # children) — the direct spawn stays.
        with open(log_path, "ab") as logf:
            proc = subprocess.Popen(
                argv, cwd=str(workspace), stdout=logf,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True, env=env)
        daemon_pid = proc.pid
    # SSE tail pointer (charter appendix): per-run log filenames need
    # a stable "latest log" resolution point.
    (logs / "daemon-current.txt").write_text(
        str(log_path), encoding="utf-8")
    # scope pointer: lets status (and the UI's per-problem Run controls)
    # answer "what is the engine working on?"
    (logs / "daemon-scope.txt").write_text(scope or "", encoding="utf-8")
    return 0, f"started daemon pid {daemon_pid}; log: {log_path}"


def daemon_stop(workspace: Path, *, force: bool = False) -> "tuple[int, str]":
    """Graceful stop by default (daemon.stop file: the tick loop stops
    spawning, drains in-flight workers, exits cleanly). force=True is the
    explicit hard-kill override; the message carries the in-flight count
    being abandoned (lease sweep + startup recovery reclaim it)."""
    from .. import dispatcher as _disp
    stop_file = _disp.stop_file_path(workspace)
    pid = _daemon_live_pid(workspace)
    if pid is None:
        fsutil.unlink_tolerant(stop_file)
        return 0, "no daemon running"
    if force:
        n = _daemon_counts(workspace)[0]
        try:
            import psutil
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=10)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
        except Exception as e:  # noqa: BLE001
            return 1, f"terminate failed: {e}"
        # Post-kill hygiene — TerminateProcess skips atexit, so nothing
        # else runs: a leftover stop-file used to wedge "stopping" into
        # the status, and the dead pid's leases rendered as running
        # agents until some future daemon start happened to sweep them
        # (scope-filtered, so possibly never).
        fsutil.unlink_tolerant(stop_file)
        released = 0
        db_path = workspace / "asterism.db"
        if db_path.exists():
            try:
                import psutil as _ps

                def _alive(owner) -> bool:
                    try:
                        o = int(owner)
                    except (TypeError, ValueError):
                        return False
                    return o != pid and _ps.pid_exists(o)
                conn = db.connect(db_path)
                released = db.release_expired_leases(
                    conn, ttl_sec=float("inf"), pid_alive=_alive)
                conn.commit()
                conn.close()
            except Exception:  # noqa: BLE001 — hygiene must not fail the stop
                released = 0
        try:
            _sc = (workspace / ".asterism" / "logs" /
                   "daemon-scope.txt").read_text(
                encoding="utf-8").strip() or None
        except OSError:
            _sc = None
        _write_exit_summary(workspace, rc=None,
                            error="force-stopped by the user", scope=_sc)
        return 0, (f"force-stopped pid {pid}; released {released} of "
                   f"{'?' if n is None else n} in-flight lease(s)")
    stop_file.write_text(db.now(), encoding="utf-8")
    return 0, (f"stop requested (graceful): daemon pid {pid} will finish "
               f"in-flight work and exit; `daemon status` to watch, "
               f"`daemon stop --force` to terminate immediately")


def cmd_daemon(args) -> int:
    """Daemon lifecycle (frontend charter §5-3): detached start / graceful
    stop / status — thin CLI shell over daemon_status/start/stop (the
    serve API imports those directly)."""
    import json as _json
    from ...core import config as _config

    workspace = _config.resolve_workspace(getattr(args, "workspace", None))
    action = args.daemon_action
    if action == "status":
        print(_json.dumps(daemon_status(workspace)))
        return 0
    if action == "start":
        code, msg = daemon_start(
            workspace, scope=getattr(args, "scope", None),
            once=getattr(args, "once", False),
            wait_lock_sec=getattr(args, "wait_lock", 0.0))
        print(msg)
        return code
    if action == "stop":
        code, msg = daemon_stop(
            workspace, force=getattr(args, "force", False))
        print(msg)
        return code
    print(f"unknown daemon action {action!r}")
    return 2


def cmd_serve(args) -> int:
    """`asterism serve` — the localhost web UI (frontend charter §0
    form A). One process per workspace; reads are connect_readonly,
    writes go through the same chokepoints the CLI uses.

    chdir to the workspace before serving: the write chokepoints
    (cmd_approve_ingest etc.) open the DB via the cwd-relative default
    path, same as every terminal invocation."""
    import uvicorn
    from ...core import config as _config
    from ...serve.app import create_app

    workspace = _config.resolve_workspace(getattr(args, "workspace", None))
    os.chdir(workspace)
    host = getattr(args, "host", None) or "127.0.0.1"
    port = int(getattr(args, "port", None) or 8642)
    app = create_app(workspace, prewarm=True)
    print(f"Asterism UI: http://{host}:{port}/  (workspace: {workspace})")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


def _force_utf8_io() -> None:
    """Force UTF-8 for this process's console I/O and for every spawned
    subprocess. On a locale-default (e.g. cp950 Traditional-Chinese)
    Windows console, emitting a char outside that codepage — a Lean goal
    routinely carries `∃` (U+2203), `∀`, `≃ᵢ`, etc. — raised
    UnicodeEncodeError mid-pipeline and was mis-recorded as a spurious
    lake_build_error (BT 2026-05-29 g3410 exists_rotation_shift_disjoint:
    3 of 5 attempts died on `cp950 can't encode '\\u2203'`, blocking a
    goal that was otherwise fine). Every framework file write already
    pins encoding='utf-8'; the gap was the inherited console encoding and
    child-process default. Reconfiguring stdout/stderr fixes this
    process's prints (and the _Tee that wraps them); exporting
    PYTHONUTF8 / PYTHONIOENCODING makes claude / lake / gateway children
    inherit UTF-8 so they don't reintroduce the crash one layer down.

    Idempotent and safe under pytest's captured streams (reconfigure is
    skipped when the stream doesn't support it)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
