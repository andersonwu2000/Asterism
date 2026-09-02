"""The RAM governor — every mechanism that decides how much Lean this
machine may hold, and takes it back when the answer shrinks.

Split out of `gateway.py` 2026-08-29 (A1-2) unchanged: the serialized
pressure outlet and its debt, the cross-platform weight cap, the
targeted wedge rescue and the heavy-slot recycle, the warm-target shed,
the mid-lease rewarm, freeze/thaw, and the warm converger. All the
shrink surgery leaves from one thread (`_weight_watchdog_run`), which
the facade's `main()` starts.

Patch the mutable globals HERE. `_PRESSURE_DEBT` is rebound under
`global`, and the histories are read by this module alone, so none of
them re-exports: a `gateway._PRESSURE_DEBT` patch would go vacuous, and
an AttributeError is the better answer.

`_compilation_for` was the last name this module reached back into the
facade for. With A1-4a it lives in `leantext`, a leaf, so the import is
module-level and the call-time workaround is gone — patch it on
`gateway.leantext`, not on the facade.
`_refresh_health_snapshot` left for `health.py` (A1-3) and is imported
from there, still at call time: that module reads `_pressure_debt` from
here, so the cycle survived the move and only changed direction.
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time

from .backend import _BACKEND_WEDGE_SEC, _restart_backend
from .elab import _elab_gate
from .leantext import _compilation_for
from .state import WARMUP_CONTENT, WorkerSlot, _state
from .weigh import _slot_private_mb, _slot_private_mb_cached, _vm_pte_bytes


#: One targeted rescue per slot per window: a SECOND wedge of the same
#: slot this soon smells like server state rot, not one runaway
#: elaboration — that shape escalates to the full restart.
_WEDGE_TARGETED_HISTORY: "dict[str, float]" = {}
_WEDGE_REPEAT_WINDOW_SEC = 1800.0

#: Cross-platform worker weight cap (owner order 2026-08-26, "先 A"):
#: the 8 GB job cap is a Windows Job Object — "Soft: None off-Windows"
#: — so on the Linux fleet nothing stopped a kernel-`decide` monster
#: from committing 27 GB mid-elaboration (Erdos p10, a 200-element
#: checksum table under maxHeartbeats 4M; the 08-08 class reached
#: 102 GB). This watchdog enforces the SAME `gateway.lean_memory_cap_mb`
#: knob by reading the same per-slot instrument and killing the one
#: over-cap worker — the elaboration fails, exactly what the Job
#: Object does on Windows. The close→reopen(warmup) that follows
#: breaks the lean server's own crash-respawn loop (it would relaunch
#: the same content and balloon again); the session's next acquire
#: reloads its content through the normal cold path.
_WEIGHT_KILL_HISTORY: "dict[str, float]" = {}
_WEIGHT_KILL_COOLDOWN_SEC = 180.0
_WEIGHT_WATCH_INTERVAL_SEC = 20.0
#: Governor pass cadence. The pressure outlet re-measures every pass;
#: the weight scan and freeze tick keep their 20 s cadence by running
#: every (interval / this) passes.
_GOVERNOR_INTERVAL_SEC = 5.0

#: Serialized pressure-release outlet (owner design 2026-08-27). While
#: the measured axes read hot, ONE free worker dies per governor pass —
#: the currently-fattest, re-weighed fresh at the kill decision — and
#: its death is confirmed before the next pass's fresh reading decides
#: again. Each kill raises this debt; the effective warm allowance is
#: `warm_target - debt`, so the converger cannot re-warm what the
#: outlet just shed. Calm passes forgive one debt step at a time, gated
#: on the pool having converged to the current allowance (the previous
#: warm landed). This replaces the ledger's open-loop integrator, which
#: wound up on release lag: 27 pause/clear cycles and 579 sheds / 597
#: warms in 7 h on the 32 GB co-tenant box (measured 2026-08-27) —
#: many "warms" mere reattaches of not-yet-dead workers, so the RAM
#: never even returned.
_PRESSURE_DEBT_LOCK = threading.Lock()
_PRESSURE_DEBT = 0


def _pressure_debt() -> int:
    with _PRESSURE_DEBT_LOCK:
        return _PRESSURE_DEBT


def _effective_target() -> "int | None":
    """The warm allowance after the pressure outlet's debt. Every
    consumer of `_state.warm_target` that sizes the pool must read
    THIS — a raw read would re-warm the outlet's kills while hot."""
    target = _state.warm_target
    if target is None:
        return None
    return max(1, target - _pressure_debt())


def _machine_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:  # noqa: BLE001 — scaling fallback
        return 32.0


def _slot_private_mb_fresh(slot: "WorkerSlot") -> "int | None":
    """ONE slot, measured NOW — the kill-decision reading. The TTL
    cache lags a full pool scan behind; at 5 GB/min inflation a stale
    reading is tens of GB wrong (a 36 GB worker slid past the 8 GB cap
    on the flagship, 2026-08-26). A candidate about to die is weighed
    fresh; everyone else stays on the cache."""
    try:
        import psutil
        pid = _worker_pid_for_uri(slot.slot_uri)
        if pid is None:
            return None
        proc = psutil.Process(pid)
        mem = proc.memory_info()
        priv = getattr(mem, "private", None)
        if priv is None:
            priv = proc.memory_full_info().uss
        return (int(priv) + _vm_pte_bytes(pid)) // (1024 * 1024)
    except Exception:  # noqa: BLE001 — unmeasurable is not zero
        return None


def _pressure_outlet_step() -> bool:
    """One measured step of the serialized release outlet. Hot: kill
    exactly one free worker (fresh-weighed fattest), confirm the death,
    raise the debt. Calm: forgive one debt step once the pool has
    converged to the current allowance. Between the bands: hold.
    Returns whether it acted (tests key on this)."""
    global _PRESSURE_DEBT
    budget = _state.ram_budget_gb
    if budget is None or _state.backend is None \
            or not _state.first_warm_done or _state.warm_target is None:
        return False
    from ...core import ram_ledger as rl
    cur = rl.framework_current_gb()
    avail = rl.available_gb()
    machine = _machine_gb()
    headroom = rl.DispatcherLedger.PRESSURE_HEADROOM_GB
    slack = rl.DispatcherLedger.PRESSURE_RELEASE_SLACK_GB
    # The resume line is the ledger's own helper, priced with the pool's
    # measured slot cost — the two processes decide the same question and
    # a second formula here would drift (2026-09-02).
    readings = _slot_private_mb_cached()
    hot = ((cur is not None and cur > budget - headroom)
           or avail < rl.pressure_low_gb(machine))
    calm = ((cur is None or cur < budget - headroom - slack)
            and avail > rl.pressure_resume_gb(
                machine, rl.slot_gb_from_readings(list(readings.values()))))
    if hot:
        candidates = sorted(
            (s for s in list(_state.workers)
             if not s.reserved and not s.closed and not s.frozen
             and not s.rewarming and s.claimed_by is None),
            key=lambda s: readings.get(s.slot_id) or 0, reverse=True)
        # Re-pick AND re-weigh: the cached order nominates, a fresh
        # reading of the top few elects (owner point: the queue is a
        # policy, not a frozen list).
        best, best_mb = None, -1
        for s in candidates[:3]:
            mb = _slot_private_mb_fresh(s)
            if mb is not None and mb > best_mb:
                best, best_mb = s, mb
        if best is None and candidates:
            best, best_mb = candidates[0], readings.get(
                candidates[0].slot_id) or 0
        if best is None:
            return False        # nothing free: admission pause +
        slot = best             # release-time sheds own the rest
        if not slot.lock.acquire(blocking=False):
            return False        # got busy since the pick: next pass
        try:
            with _state.sessions_lock:
                if slot.claimed_by is not None or slot.closed \
                        or slot.frozen:
                    return False
                if _open_pipeline_slots_locked() <= 1:
                    return False    # anti-starvation floor
                slot.closed = True
            try:
                _state.backend.did_close(slot.slot_path)
            except Exception:  # noqa: BLE001 — the kill below settles it
                pass
            if not _await_worker_exit(slot.slot_uri):
                _kill_worker_for_uri(slot.slot_uri)
            with _PRESSURE_DEBT_LOCK:
                _PRESSURE_DEBT += 1
                debt = _PRESSURE_DEBT
            cur_s = "n/a" if cur is None else f"{cur:.1f}G"
            print(f"[gateway] pressure shed — slot {slot.slot_id} "
                  f"({best_mb} MB fresh) killed and confirmed dead "
                  f"(available {avail:.1f}G, cgroup {cur_s}); outlet "
                  f"debt {debt}", file=sys.stderr, flush=True)
            return True
        finally:
            slot.lock.release()
    if calm and _pressure_debt() > 0:
        target = _effective_target()
        with _state.sessions_lock:
            converged = (target is not None
                         and _open_pipeline_slots_locked() >= target)
        if converged:
            with _PRESSURE_DEBT_LOCK:
                _PRESSURE_DEBT = max(0, _PRESSURE_DEBT - 1)
                debt = _PRESSURE_DEBT
            print(f"[gateway] pressure debt forgiven — one step "
                  f"(available {avail:.1f}G, {debt} remaining); the "
                  f"converger may warm one", file=sys.stderr, flush=True)
            _kick_warm_converger()
            return True
    return False


def _weight_kill_over_cap() -> int:
    """One scan: kill every worker whose private+PTE reading exceeds
    the cap. Returns the number killed (for tests and the log)."""
    backend = _state.backend
    if backend is None or not _state.first_warm_done:
        return 0
    cap_mb = SLOT_RECYCLE_MB_DEFAULT * 5  # unreachable fallback
    try:
        from ...core import config as _cfg
        cap_mb = int(_cfg.get("gateway.lean_memory_cap_mb", default=8192,
                              env_var="ASTERISM_LEAN_MEMORY_CAP_MB",
                              cast=int))
    except Exception:  # noqa: BLE001 — a config hiccup must not kill
        return 0
    if cap_mb <= 0:
        return 0
    killed = 0
    now = time.monotonic()
    readings = _slot_private_mb_cached()
    for slot in list(_state.workers):
        if slot.closed:
            continue
        mb = readings.get(slot.slot_id)
        if mb is None or mb <= cap_mb:
            continue
        last = _WEIGHT_KILL_HISTORY.get(slot.slot_uri)
        if last is not None and now - last < _WEIGHT_KILL_COOLDOWN_SEC:
            continue
        # The cache nominates, a fresh reading convicts: the TTL scan
        # lags, and killing on a stale number executes the wrong worker
        # (or misses the right one — a 36 GB monster slid past this cap
        # on stale readings, flagship 2026-08-26).
        fresh = _slot_private_mb_fresh(slot)
        if fresh is None or fresh <= cap_mb:
            print(f"[gateway] slot {slot.slot_id} spared by the fresh "
                  f"reading — cache said {mb} MB, the scale says "
                  f"{fresh} MB (cap {cap_mb} MB)",
                  file=sys.stderr, flush=True)
            continue
        mb = fresh
        _WEIGHT_KILL_HISTORY[slot.slot_uri] = now
        print(f"[gateway] slot {slot.slot_id} worker over the memory cap "
              f"— {mb} MB > {cap_mb} MB — killed mid-elaboration (the "
              f"in-flight call fails, same semantics as the Windows job "
              f"cap). Its document reopens on warmup content.",
              file=sys.stderr, flush=True)
        _kill_worker_for_uri(slot.slot_uri)
        with contextlib.suppress(Exception):
            backend.did_close(slot.slot_path)
        with contextlib.suppress(Exception):
            backend.did_open(slot.slot_path, WARMUP_CONTENT)
        slot.content_pipeline_id = None
        killed += 1
    return killed


def _weight_watchdog_run() -> None:
    """The governor thread: every pass runs one pressure-outlet step
    (measure → at most one kill or one forgiveness → measure again next
    pass) and refreshes the /health snapshot; the weight scan and the
    freeze tick keep their slower cadence. One thread on purpose — all
    the shrink surgery leaves from a single outlet, so the knives never
    race each other on stale readings."""
    passes_per_scan = max(1, int(_WEIGHT_WATCH_INTERVAL_SEC
                                 / _GOVERNOR_INTERVAL_SEC))
    n = 0
    while True:
        time.sleep(_GOVERNOR_INTERVAL_SEC)
        n += 1
        try:
            _pressure_outlet_step()
        except Exception as exc:  # noqa: BLE001 — the governor survives
            print(f"[gateway] pressure outlet step failed "
                  f"({type(exc).__name__}: {exc})", file=sys.stderr,
                  flush=True)
        # Call-time, per pass: the health axis reads this module's
        # `_pressure_debt`, so a module-level import of it here would
        # close a cycle.
        from .health import _refresh_health_snapshot
        try:
            _refresh_health_snapshot()
        except Exception as exc:  # noqa: BLE001 — the governor survives
            print(f"[gateway] health snapshot refresh failed "
                  f"({type(exc).__name__}: {exc})", file=sys.stderr,
                  flush=True)
        if n % passes_per_scan:
            continue
        try:
            _weight_kill_over_cap()
        except Exception as exc:  # noqa: BLE001 — the watchdog survives
            print(f"[gateway] weight watchdog scan failed "
                  f"({type(exc).__name__}: {exc})", file=sys.stderr,
                  flush=True)
        try:
            _freeze_tick()
        except Exception as exc:  # noqa: BLE001 — the watchdog survives
            print(f"[gateway] freeze tick failed "
                  f"({type(exc).__name__}: {exc})", file=sys.stderr,
                  flush=True)


def _kill_worker_for_uri(uri: str) -> bool:
    """Tree-kill the ONE `lean --worker` process serving `uri`.

    The mapping is exact for the same reason `_slot_private_mb`'s is:
    Lean puts the document URI on the worker's own command line, so
    nothing depends on process order. Returns whether a worker was
    actually killed."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        killed = False
        for proc in me.children(recursive=True):
            try:
                argv = proc.cmdline()
            except (psutil.Error, OSError):
                continue
            if "--worker" not in argv or uri not in argv:
                continue
            for child in proc.children(recursive=True):
                with contextlib.suppress(Exception):
                    child.kill()
            with contextlib.suppress(Exception):
                proc.kill()
                killed = True
        return killed
    except Exception:  # noqa: BLE001 — the caller escalates instead
        return False


def _recycle_wedged_slot(uri: str) -> bool:
    """Targeted wedge recovery: kill the one runaway worker and re-warm
    ITS slot, leaving every other slot's claim intact.

    Scale motive (owner ruling 2026-08-24): 166 whole-pool restarts on
    record, each stripping EVERY in-flight session of its slot claim
    plus a cold content re-warm (420 victims at pool 4-12) — at cloud
    pool sizes one wedge would take ~50 live formalizers' Lean surface
    down at once. The close/re-open flow is `_recycle_slot_if_heavy`'s,
    in production since 2026-08-14.

    Returns True when the slot is back in the pool. False hands the
    wedge to `_restart_backend` — the pre-2026-08-24 behavior, kept as
    the escalation for every shape this path cannot prove it fixed
    (repeat wedge of the same slot, claim-lock held by a live request,
    worker not found, re-open failure)."""
    now = time.monotonic()
    last = _WEDGE_TARGETED_HISTORY.get(uri)
    if last is not None and now - last < _WEDGE_REPEAT_WINDOW_SEC:
        return False
    backend = _state.backend
    slot = next((s for s in _state.workers if s.slot_uri == uri), None)
    if backend is None or slot is None:
        return False
    if not slot.lock.acquire(blocking=False):
        # A request thread is mid-call on this slot; yanking the worker
        # under it risks a half-state the full restart already handles.
        return False
    try:
        if not _kill_worker_for_uri(uri):
            return False
        try:
            with contextlib.suppress(Exception):
                backend.did_close(slot.slot_path)
            backend.did_open(slot.slot_path, WARMUP_CONTENT)
            backend.wait_for_file_done(slot.slot_uri, timeout=300)
        except Exception:  # noqa: BLE001 — escalation handles it
            return False
        # Claim cleared: the owning session re-claims on its next call
        # and pays ONE cold content warm — the price every session paid
        # under the whole-pool restart, now paid by one.
        slot.claimed_by = None
        slot.content_pipeline_id = None
        _WEDGE_TARGETED_HISTORY[uri] = now
        print(f"[gateway] wedged worker on slot {slot.slot_id} killed "
              f"and recycled — every other slot keeps its claim",
              file=sys.stderr, flush=True)
        return True
    finally:
        slot.lock.release()


def _wedge_watchdog_loop() -> None:
    """Replace the backend if any slot's Lean elaborate has been in-flight
    past `_BACKEND_WEDGE_SEC` — a non-terminating elaborate, well beyond
    the 120s per-op / 300s warmup waits."""
    nonempty_since: dict[str, float] = {}
    while True:
        time.sleep(30.0)
        backend = _state.backend
        if backend is None or not _state.ready_event.is_set():
            nonempty_since.clear()
            continue
        now = time.monotonic()
        try:
            busy = backend.busy_uris()
        except Exception:
            continue
        for uri in list(nonempty_since):
            if uri not in busy:
                nonempty_since.pop(uri, None)
        wedged = None
        for uri in busy:
            t0 = nonempty_since.setdefault(uri, now)
            if now - t0 > _BACKEND_WEDGE_SEC:
                wedged = uri
                break
        if wedged is not None:
            nonempty_since.clear()
            if not _recycle_wedged_slot(wedged):
                _restart_backend(
                    f"elaborate on {wedged} wedged "
                    f">{int(_BACKEND_WEDGE_SEC)}s")


#: A slot whose worker holds more private bytes than this is recycled
#: when it next falls idle and unclaimed. 0 disables.
#:
#: DELIBERATELY far below `gateway.lean_memory_cap_mb` (8192), because
#: the two answer different questions and must not be collapsed:
#:
#:   the job cap   how much may ONE elaboration commit before the OS
#:                 kills it — a hard ceiling against the 102 GB worker
#:                 that took the box down on 2026-08-10.
#:   this          how fat may a slot get ACROSS elaborations before it
#:                 is cheaper to start it over. Soft, and it swaps a
#:                 process rather than killing work.
#:
#: Measured 2026-08-14 on union_closed: baseline 0.65-0.8 GB (Mathlib +
#: the problem's 285-brick closure), and a claimed slot serving the
#: `decide`-heavy 634 family reached 2.58 GB in ~36 minutes and then sat
#: flat. 1500 sits above every observed baseline and below every
#: observed fat slot.
# One home for the threshold: the RAM ledger prices slots at this same
# ceiling (`ram_ledger.slot_recycle_gb`), so the two knobs move
# together.
from ...core.ram_ledger import SLOT_RECYCLE_MB_DEFAULT  # noqa: E402


def _worker_pid_for_uri(slot_uri: str) -> "int | None":
    """PID of the live `--worker` process serving this slot URI, or
    None. The mapping is exact for the same reason `_slot_private_mb`'s
    is: Lean puts the document URI on the worker's own command line."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        for proc in me.children(recursive=True):
            try:
                argv = proc.cmdline()
            except (psutil.Error, OSError):
                continue
            if "--worker" in argv and slot_uri in argv:
                return proc.pid
    except Exception:  # noqa: BLE001 — a probe, never a failure source
        pass
    return None


WORKER_EXIT_WAIT_SEC = 15.0


def _await_worker_exit(slot_uri: str,
                       timeout: float = WORKER_EXIT_WAIT_SEC) -> bool:
    """After a didClose, wait for the slot's worker process to actually
    die before reopening the document.

    didClose is a NOTIFICATION — the worker's death is asynchronous,
    and a didOpen for the same URI that lands first makes the server
    keep the same process and therefore the same heap. That race made
    the recycle a no-op 308 times out of 315 ("recycled in 0.0s —
    5831 MB -> 5831 MB"; measured 2026-08-26): the 1500 MB policy
    existed only on paper while slots grew to 3-5.8 GB, and on the
    128 GB fleet the fattened pool evicted the shared mathlib page
    cache into a refault storm (load 60 on 8 cores, memory PSI full
    83%).

    True = the worker is gone (also when none was found: already dead,
    or unmeasurable — reopening is the only move either way). False =
    it survived the wait; the caller escalates (hard kill) before the
    reopen — a reattach would keep the old heap and lie about it.
    """
    try:
        import psutil
    except Exception:  # noqa: BLE001 — no instrument, no wait
        return True
    pid = _worker_pid_for_uri(slot_uri)
    if pid is None:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            proc = psutil.Process(pid)
            if not proc.is_running() \
                    or proc.status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        except (psutil.Error, OSError):
            return True
        time.sleep(0.2)
    return False


def _recycle_slot_if_heavy(slot: "WorkerSlot") -> None:
    """Restart one slot's worker if it has grown fat — close the
    document, re-open it warm.

    WHEN. Only at this boundary, and only on a slot that is unclaimed
    and not busy. That makes the timing free without having to detect
    it: the NL layer (Strategist, Adversary, Scholar, Librarian) never
    registers a session at all — `write_tools_mcp_config`, not
    `_write_mcp_config` — so a debate round is minutes of Lean idleness,
    and this lands in it by construction rather than by asking what
    time it is.

    WHY A CLOSE. `did_change_full` swaps the content and keeps the
    process; the heap is what needs to go, so the document has to.

    NOT THE OTHER TWO MECHANISMS. The job cap kills a runaway single
    elaboration; the wedge watchdog restarts the backend when an
    elaborate hangs past 600s — and that one, by construction, only ever
    fires while Lean is BUSY. Neither can do this and this can do
    neither: a slot at 2.6 GB is not wedged and not over any cap, it is
    just expensive to keep.

    Failure leaves the slot OPEN. A recycle that half-completes would
    take a worker out of the pool for the rest of the run, which is a
    worse outcome than any amount of memory, so the re-open is attempted
    again on the error path and the failure is printed rather than
    raised.
    """
    cap_mb = SLOT_RECYCLE_MB_DEFAULT
    try:
        from ...core import config as _cfg
        cap_mb = int(_cfg.get("gateway.slot_recycle_mb",
                              default=SLOT_RECYCLE_MB_DEFAULT,
                              env_var="ASTERISM_SLOT_RECYCLE_MB",
                              cast=int))
    except Exception:  # noqa: BLE001 — a policy knob may not halt release
        pass
    if cap_mb <= 0 or _state.backend is None:
        return
    if not slot.lock.acquire(blocking=False):
        return                      # busy: not ours to touch
    try:
        if slot.claimed_by is not None:
            return                  # re-claimed between release and here
        mb = _slot_private_mb().get(slot.slot_id)
        if mb is None or mb < cap_mb:
            return
        print(f"[gateway] slot {slot.slot_id} recycling — {mb} MB private "
              f"(> {cap_mb} MB) and idle. Its worker restarts; no session "
              f"holds it.", file=sys.stderr, flush=True)
        t0 = time.perf_counter()
        try:
            _state.backend.did_close(slot.slot_path)
            # The whole point is a FRESH worker — see _await_worker_exit
            # for the race that made this a silent no-op for months.
            # Escalation is the wedge path's proven kill: a reattach
            # would keep the old heap and lie about it.
            if not _await_worker_exit(slot.slot_uri):
                _kill_worker_for_uri(slot.slot_uri)
                print(f"[gateway] slot {slot.slot_id} recycle: worker "
                      f"survived didClose for {WORKER_EXIT_WAIT_SEC:.0f}s "
                      f"— hard-killed before the reopen",
                      file=sys.stderr, flush=True)
            _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
            _state.backend.wait_for_file_done(slot.slot_uri, timeout=300)
            after = _slot_private_mb().get(slot.slot_id)
            print(f"[gateway] slot {slot.slot_id} recycled in "
                  f"{time.perf_counter() - t0:.1f}s — "
                  f"{mb} MB -> {after if after is not None else '?'} MB",
                  file=sys.stderr, flush=True)
        except Exception as exc:  # noqa: BLE001 — never lose a slot
            print(f"[gateway] slot {slot.slot_id} recycle FAILED "
                  f"({type(exc).__name__}: {exc}) — re-opening so the "
                  f"slot stays in the pool", file=sys.stderr, flush=True)
            try:
                _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
            except Exception:  # noqa: BLE001
                print(f"[gateway] slot {slot.slot_id} could not be "
                      f"re-opened — it will cold-warm on its next claim",
                      file=sys.stderr, flush=True)
    finally:
        slot.lock.release()


# ─── Adaptive warm target (RAM ledger, owner design 2026-08-25) ──
#
# The dispatcher's ledger computes how many Lean slots the RAM budget
# affords once the NL layer's reserve is taken out, and POSTs it to
# /warm_target. Convergence is asymmetric on purpose:
#   * UP: a background converger re-opens closed slots (or extends the
#     roster) one warm at a time, vetoed by measured available RAM.
#   * DOWN: nothing is revoked — a claimed slot finishes its work; the
#     shed lands at release time, where closing the slot (did_close)
#     actually frees the worker's heap.
# Static mode (warm_target is None) leaves all of this dormant.


def _open_pipeline_slots_locked() -> int:
    """Non-reserved slots with a live worker. Caller holds
    sessions_lock."""
    return sum(1 for s in _state.workers
               if not s.reserved and not s.closed)


def _shed_slot_if_over_target(slot: WorkerSlot) -> bool:
    """Close a just-released slot when the warm target sits below the
    open count — its worker exits and the RAM returns to the ledger's
    NL side. Returns whether the slot was shed. The floor of one open
    slot is the Lean side's anti-starvation guarantee (owner ruling:
    NL has priority, but never to zero)."""
    target = _effective_target()
    if target is None or _state.backend is None:
        return False
    if not slot.lock.acquire(blocking=False):
        return False                # busy: not ours to touch
    try:
        with _state.sessions_lock:
            if slot.claimed_by is not None or slot.closed or slot.reserved:
                return False
            if _open_pipeline_slots_locked() <= max(1, target):
                return False
            slot.closed = True      # invisible to claims from here on
        try:
            _state.backend.did_close(slot.slot_path)
            print(f"[gateway] slot {slot.slot_id} shed — open count above "
                  f"warm target {target}; its worker exits and the RAM "
                  f"returns to the ledger", file=sys.stderr, flush=True)
            return True
        except Exception as exc:  # noqa: BLE001 — never lose a slot
            with _state.sessions_lock:
                slot.closed = False
            print(f"[gateway] slot {slot.slot_id} shed FAILED "
                  f"({type(exc).__name__}: {exc}) — slot stays open",
                  file=sys.stderr, flush=True)
            return False
    finally:
        slot.lock.release()


#: Residue allowance factor: rewarm when the worker sits MORE than
#: this many recycle-thresholds above its content's own measured need
#: (the baseline). Derived, not pinned (one fact, one home): the
#: recycle threshold is the framework's declared "dead heap worth a
#: FREE restart at release"; a mid-lease restart can block a tool
#: call, so it demands twice the loot. Absolute thresholds judged the
#: union_closed decide-monsters by their legitimate 5 GB size and
#: churned a rewarm loop on them (one pass hit the 600s elab wall and
#: pinned the slot for 10 minutes, 2026-08-26); the baseline delta
#: cannot make that mistake.
_MIDLEASE_RESIDUE_FACTOR = 2.0
#: Short — only bridges the reading cache's TTL after a rewarm so the
#: stale fat reading cannot re-trigger before the fresh baseline is
#: visible (the baseline reset is the real anti-churn mechanism).
_MIDLEASE_COOLDOWN_SEC = 60.0


def _midlease_residue_mb() -> int:
    """Env absolute override, else factor x the recycle threshold
    (same knob the release-time recycle and the ledger price read)."""
    import os as _os
    try:
        v = int(_os.environ.get("ASTERISM_MIDLEASE_RESIDUE_MB", ""))
        if v > 0:
            return v
    except ValueError:
        pass
    cap_mb = SLOT_RECYCLE_MB_DEFAULT
    try:
        from ...core import config as _cfg
        cap_mb = int(_cfg.get("gateway.slot_recycle_mb",
                              default=SLOT_RECYCLE_MB_DEFAULT,
                              env_var="ASTERISM_SLOT_RECYCLE_MB", cast=int))
    except Exception:  # noqa: BLE001 — policy knob must not break tools
        pass
    return int(max(1, cap_mb) * _MIDLEASE_RESIDUE_FACTOR)


def _maybe_kick_midlease_rewarm(slot: WorkerSlot, meta) -> None:
    """Owner design 2026-08-26 ("tool 已算好返回結果時偵測 slot 大小,
    太肥就重暖放回代碼"): called right after a tool call returns its
    result — the one moment the worker is provably idle and the agent
    is about to think for minutes, so the restart overlaps a window
    where nobody is waiting. Recycle-at-release cannot reach a fat
    worker mid-lease; this can, and it reuses recycle's proven kill
    (`_await_worker_exit` + hard kill — a reattach would keep the old
    heap).

    The judgment is BASELINE-RELATIVE (owner insight 2026-08-26: fat
    is classified by WHEN it grew): weight at the content's first
    return is the content's own need; only growth beyond it across
    later calls is residue. See `WorkerSlot.content_baseline_mb`."""
    if meta is None or _state.backend is None:
        return
    if slot.rewarming or slot.closed or slot.reserved or slot.frozen:
        return
    # rewarmed_at=0.0 means "never" — and uptime-anchored monotonic()
    # reads 0.0 as "recent" on a young machine (the ram_ledger
    # first-push lesson), so a never-rewarmed slot gets no cooldown.
    if slot.rewarmed_at \
            and time.monotonic() - slot.rewarmed_at < _MIDLEASE_COOLDOWN_SEC:
        return
    mb = _slot_private_mb_cached().get(slot.slot_id)
    if mb is None:
        return
    if slot.baseline_for != slot.content_pipeline_id \
            or slot.content_baseline_mb is None:
        # First return since this content landed: this weight IS the
        # content's own need. Measure, never judge.
        slot.content_baseline_mb = mb
        slot.baseline_for = slot.content_pipeline_id
        return
    if mb - slot.content_baseline_mb < _midlease_residue_mb():
        return
    slot.rewarming = True
    threading.Thread(target=_midlease_rewarm_run, args=(slot, meta, mb),
                     name=f"midlease-rewarm-{slot.slot_id}",
                     daemon=True).start()


def _rebuild_worker(slot: WorkerSlot, meta) -> "int | None":
    """Kill-then-fresh-didOpen with the session's merged unit — the
    shared core of the mid-lease rewarm and the freeze thaw. Caller
    holds slot.lock. Content is computed BEFORE the close (a failure
    must leave whatever worker exists running); a failed reopen falls
    back to warmup so the slot is never bricked, then re-raises.
    Returns the fresh weight reading and resets the residue baseline."""
    backend = _state.backend
    merged, line_map = _compilation_for(meta)
    with contextlib.suppress(Exception):
        backend.did_close(slot.slot_path)
    if not _await_worker_exit(slot.slot_uri):
        _kill_worker_for_uri(slot.slot_uri)
    try:
        with _elab_gate(slot.slot_uri, None):
            slot.slot_path.write_text(merged, encoding="utf-8")
            backend.did_open(slot.slot_path, merged)
            try:
                backend.wait_for_file_done(slot.slot_uri, timeout=600)
            except (TimeoutError, RuntimeError):
                pass
        slot.file_version = 1
        slot.line_map = line_map
        slot.content_pipeline_id = meta.pipeline_id
    except Exception:  # noqa: BLE001 — never brick the slot
        try:
            backend.did_open(slot.slot_path, WARMUP_CONTENT)
            slot.file_version = 1
            slot.content_pipeline_id = None
        except Exception:  # noqa: BLE001
            pass
        raise
    after = _slot_private_mb().get(slot.slot_id)
    # The fresh worker's weight with this content = the new baseline
    # (anti-churn: the next residue delta starts from here).
    slot.content_baseline_mb = after
    slot.baseline_for = slot.content_pipeline_id
    return after


def _midlease_rewarm_run(slot: WorkerSlot, meta, before_mb: int) -> None:
    """Background half: restart the fat worker and put the session's
    content back (fresh didOpen carries the merged compilation unit, so
    base import + content elaborate in one pass, under the elab gate —
    it is real work). Holds slot.lock throughout; an early tool call
    queues on the lock and `_acquire_slot` credits the wait."""
    t0 = time.perf_counter()
    try:
        if not slot.lock.acquire(timeout=60):
            return                    # agent came back instantly; skip
        try:
            with _state.sessions_lock:
                if slot.claimed_by != meta.pipeline_id or slot.closed:
                    return
            backend = _state.backend
            if backend is None:
                return
            after = _rebuild_worker(slot, meta)
            print(f"[gateway] slot {slot.slot_id} mid-lease rewarm in "
                  f"{time.perf_counter() - t0:.1f}s — {before_mb} MB -> "
                  f"{after if after is not None else '?'} MB (content "
                  f"restored for {meta.pipeline_id[:8]}; baseline reset)",
                  file=sys.stderr, flush=True)
        finally:
            slot.lock.release()
    except Exception as exc:  # noqa: BLE001 — housekeeping never raises
        print(f"[gateway] mid-lease rewarm of slot {slot.slot_id} FAILED "
              f"({type(exc).__name__}: {exc}) — worker state restored "
              f"best-effort; cooldown applies", file=sys.stderr, flush=True)
    finally:
        slot.rewarmed_at = time.monotonic()
        slot.rewarming = False


#: Freeze/thaw hysteresis (owner design 2026-08-26): freezing starts
#: the moment the cgroup's true footprint crosses the BUDGET itself
#: (the pause line 8G below it already stopped reinforcements); thaw
#: resumes one slot per scan once comfortably back under. Busy workers
#: are only frozen under deep overshoot — killing mid-elaboration
#: costs the in-flight call, the same price the weight cap charges.
_FREEZE_THAW_SLACK_GB = 6.0
_FREEZE_BUSY_ESCALATION_GB = 4.0
#: Absolute bound on how long one tool call may queue on a frozen
#: slot before it errors out loud — a thaw that never comes must not
#: hold a session hostage silently.
_FROZEN_WAIT_MAX_SEC = 1800.0


def _unfrozen_open_count() -> int:
    return sum(1 for s in _state.workers
               if not s.reserved and not s.closed and not s.frozen)


def _freeze_slot(slot: WorkerSlot, mb: int, busy: bool) -> bool:
    """Kill the worker, keep the session and its claim. Idle slots
    freeze under their lock; a busy escalation kills mid-elaboration
    (the in-flight call fails)."""
    backend = _state.backend
    if backend is None:
        return False
    if busy:
        slot.frozen = True
        slot.frozen_at = time.monotonic()
        _kill_worker_for_uri(slot.slot_uri)
        with contextlib.suppress(Exception):
            backend.did_close(slot.slot_path)
        print(f"[gateway] slot {slot.slot_id} FROZEN mid-elaboration — "
              f"{mb} MB returned to the machine; the in-flight call "
              f"fails, the session survives and thaws when pressure "
              f"clears", file=sys.stderr, flush=True)
        return True
    if not slot.lock.acquire(blocking=False):
        return False
    try:
        if slot.closed or slot.frozen:
            return False
        slot.frozen = True
        slot.frozen_at = time.monotonic()
        with contextlib.suppress(Exception):
            backend.did_close(slot.slot_path)
        if not _await_worker_exit(slot.slot_uri):
            _kill_worker_for_uri(slot.slot_uri)
        print(f"[gateway] slot {slot.slot_id} FROZEN — {mb} MB returned "
              f"to the machine; its session keeps the claim, tool calls "
              f"queue with wall credit until the thaw",
              file=sys.stderr, flush=True)
        return True
    finally:
        slot.lock.release()


def _thaw_slot(slot: WorkerSlot) -> None:
    """Give the frozen slot a worker back — on WARMUP content, never the
    session's own file (owner ruling 2026-08-29). The freeze is the RAM
    axis's business: it took the worker's heap and kept the session's
    claim; the thaw returns a slot, and that is all it owes. Restoring
    the session's content here meant a full re-elaboration inside the
    thaw — it queued on the elaboration lanes (600s on the 4-OCPU
    flagship), failed loudly, and handed the agent a message with no
    action in it. Now the thaw is a ~1s reopen that needs no lane and
    cannot fail in any way the agent should hear about; the owner's
    next tool call swaps its content back in under the elaboration gate
    with the usual queue credit, exactly like a cold claim."""
    if not slot.lock.acquire(timeout=10):
        return
    try:
        if not slot.frozen:
            return
        t0 = time.perf_counter()
        try:
            _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
        except Exception as exc:  # noqa: BLE001 — the wedge path owns it
            print(f"[gateway] thaw of slot {slot.slot_id} could not reopen "
                  f"warmup ({type(exc).__name__}: {exc}) — left frozen for "
                  f"the next scan", file=sys.stderr, flush=True)
            return
        slot.file_version = 1
        slot.content_pipeline_id = None
        slot.line_map = None
        slot.frozen = False
        print(f"[gateway] slot {slot.slot_id} THAWED to warmup in "
              f"{time.perf_counter() - t0:.1f}s — "
              f"{'owner ' + slot.claimed_by[:8] + ' reloads on its next call' if slot.claimed_by else 'unclaimed'}",
              file=sys.stderr, flush=True)
    finally:
        slot.thaw_waiting = False
        slot.lock.release()


def _freeze_tick() -> int:
    """One scan of the fleet-level pressure answer: over budget ->
    freeze the fattest idle workers until the estimate is back under;
    comfortably under -> thaw one (waiters first, then oldest)."""
    budget = _state.ram_budget_gb
    if budget is None or _state.backend is None \
            or not _state.first_warm_done:
        return 0
    from ...core import ram_ledger as _rl
    cur = _rl.framework_current_gb()
    if cur is None:
        return 0
    acted = 0
    if cur > budget:
        readings = _slot_private_mb_cached()
        est = cur
        for s in sorted(
                (s for s in list(_state.workers)
                 if not s.reserved and not s.closed and not s.frozen
                 and not s.rewarming),
                key=lambda s: readings.get(s.slot_id) or 0,
                reverse=True):
            if est <= budget or _unfrozen_open_count() <= 1:
                break
            mb = readings.get(s.slot_id) or 0
            if mb <= 0:
                continue
            busy = s.lock.locked()
            if busy and est <= budget + _FREEZE_BUSY_ESCALATION_GB:
                continue
            if _freeze_slot(s, mb, busy):
                est -= mb / 1024.0
                acted += 1
    elif cur < budget - _FREEZE_THAW_SLACK_GB:
        frozen = [s for s in list(_state.workers) if s.frozen]
        if frozen:
            frozen.sort(key=lambda s: (not s.thaw_waiting, s.frozen_at))
            _thaw_slot(frozen[0])
            acted += 1
    return acted


def _kick_warm_converger() -> None:
    """Start the background convergence loop (single-flight)."""
    with _state.sessions_lock:
        if _state.warm_converger_on:
            return
        _state.warm_converger_on = True
    threading.Thread(target=_warm_converger_run,
                     name="warm-converger", daemon=True).start()


def _warm_converger_run() -> None:
    """Converge the open-slot count toward the target, one slot at a
    time — BOTH directions: warms below it, sheds idle FREE slots above
    it (a target drop with 20 already-free slots must return their RAM
    now, not wait for sessions that will never release them — external
    review 2026-08-25). Busy/claimed slots above target still shed at
    their own release. Exits when converged, when the measured-RAM veto
    fires, or in static mode; the dispatcher re-pushes the target on
    its ledger tick, so an early exit is re-kicked within seconds."""
    try:
        while True:
            target = _effective_target()
            if target is None or _state.backend is None \
                    or _state.workspace is None \
                    or not _state.first_warm_done:
                # Never converge concurrently with the INITIAL warm —
                # both would mint slot ids from the same (still empty)
                # roster and race on the same slot files.
                return
            with _state.sessions_lock:
                open_n = _open_pipeline_slots_locked()
            if open_n > max(1, target):
                # Downward FIRST, and never vetoed: shedding is how
                # RAM pressure gets relieved — gating it on available
                # RAM would deadlock exactly when it matters. The shed
                # helper re-checks claim/busy/floor under its own
                # locks; nothing idle left → the release path owns
                # the rest.
                # Shed the FATTEST free slot first (owner call
                # 2026-08-26): once a slot is free its residual content
                # has no owner — the only asset every candidate shares
                # is the warm base import — so the re-warm price is
                # identical whichever dies, and the fat one returns the
                # most RAM per kill.
                _readings = _slot_private_mb_cached()
                shed_any = False
                for s in sorted(
                        (s for s in list(_state.workers)
                         if not s.reserved and not s.closed
                         and s.claimed_by is None),
                        key=lambda s: _readings.get(s.slot_id) or 0,
                        reverse=True):
                    if _shed_slot_if_over_target(s):
                        shed_any = True
                        break
                if not shed_any:
                    return
                continue
            # Upward from here — the measured veto applies to WARMS
            # only.
            floor = _state.warm_min_available_gb
            if floor > 0:
                try:
                    from ...core import ram_ledger
                    if ram_ledger.available_gb() < floor \
                            + ram_ledger.SLOT_GB_FALLBACK:
                        print(f"[gateway] warm-converger paused — "
                              f"available RAM under the ledger floor "
                              f"({floor:.1f} GB + one slot)",
                              file=sys.stderr, flush=True)
                        return
                except Exception:  # noqa: BLE001 — veto is best-effort
                    pass
            slot: "WorkerSlot | None" = None
            with _state.sessions_lock:
                if _open_pipeline_slots_locked() >= target:
                    return
                slot = next((s for s in _state.workers
                             if s.closed and not s.reserved), None)
                if slot is None:
                    new_id = max((s.slot_id for s in _state.workers),
                                 default=-1) + 1
                    slots_dir = (_state.workspace / ".asterism"
                                 / "runtime_slots")
                    slot_path = slots_dir / f"_gateway_slot_{new_id}.lean"
                    slot = WorkerSlot(
                        slot_id=new_id, slot_path=slot_path,
                        slot_uri=slot_path.as_uri(), closed=True)
                    _state.workers.append(slot)
            if not slot.lock.acquire(blocking=False):
                time.sleep(0.5)
                continue
            try:
                t0 = time.perf_counter()
                slot.slot_path.parent.mkdir(parents=True, exist_ok=True)
                slot.slot_path.write_text(WARMUP_CONTENT, encoding="utf-8")
                # No _await_worker_exit here ON PURPOSE: reattaching a
                # shed-but-not-yet-dead worker (a 0.0s "warm") CANCELS
                # the shed cheaply, and the slot is counted as open
                # again either way. Only the recycle needs the death —
                # its point is the fresh heap.
                _state.backend.did_open(slot.slot_path, WARMUP_CONTENT)
                _state.backend.wait_for_file_done(slot.slot_uri,
                                                  timeout=300)
                with _state.sessions_lock:
                    slot.closed = False
                print(f"[gateway] slot {slot.slot_id} warmed by the "
                      f"converger in {time.perf_counter() - t0:.1f}s "
                      f"(target {target})", file=sys.stderr, flush=True)
            except Exception as exc:  # noqa: BLE001 — keep converging
                print(f"[gateway] converger warm of slot {slot.slot_id} "
                      f"FAILED ({type(exc).__name__}: {exc}) — slot stays "
                      f"closed; next ledger tick retries",
                      file=sys.stderr, flush=True)
                try:
                    _state.backend.did_close(slot.slot_path)
                except Exception:  # noqa: BLE001
                    pass
                return
            finally:
                slot.lock.release()
    finally:
        with _state.sessions_lock:
            _state.warm_converger_on = False
