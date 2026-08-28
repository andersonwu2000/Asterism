"""Session lifecycle — the claim that binds one pipeline to one slot.

Split out of `gateway.py` 2026-08-29 (A1-3) unchanged: the borrow order
a probe walks, the acquire context manager every tool op enters,
register/release, the contextvar lookup, and the stale-claim sweep that
takes a slot back from an owner that died.

Nothing here reaches back into the package `__init__` any more. The two
call-time imports this module was born with closed with A1-4a:
`_log_for` moved to `state` and `_compilation_for` to `leantext`, both
leaves, so both are imported at module level. A module-level import
COPIES the binding into this namespace, so everything resolved here is
patched as `gateway.sessions.<name>` — that is what the register-side
`_ensure_backend_ready` test does, and what `_compilation_for` now needs
too. `gateway.governor.…` is the target only for the verbs
`_release_session_internal` and `_acquire_slot` call INTO (the freeze
ceiling, shed/recycle/rewarm), which resolve in the governor's own
namespace.

`_echo_removed` and its `_ECHO_END_CHARS` left for `rpc.py` with 4a:
`apply_edit` was their only consumer, and what an edit removed is a tool
answer, not part of the session lifecycle.

`_owner_alive` and `_SWEEP_INTERVAL_SEC` do not re-export: their only
consumers are in this file, so a facade patch would go vacuous and an
AttributeError is the better answer.
"""
from __future__ import annotations

import contextlib
import sys
import time
import uuid
from pathlib import Path

from .backend import _ensure_backend_ready
from .elab import _elab_gate, _record_queue_credit
from .governor import (
    _FROZEN_WAIT_MAX_SEC,
    _maybe_kick_midlease_rewarm,
    _recycle_slot_if_heavy,
    _shed_slot_if_over_target,
)
from .leantext import _compilation_for
from .state import (
    SessionMetadata,
    WorkerSlot,
    _log_for,
    _session_ctx,
    _state,
)


# ─── Slot acquisition (the heart of Phase 2) ─────────────

def _borrow_order(workers):
    """Slot preference for a borrow probe: UNCLAIMED slots first (evicting a
    registered session's warm content costs its owner a cold_warmup and can
    block it behind our lock — the 2026-06-29 slot-thrash shape), LRU within
    each group. A claimed slot is reachable only when every unclaimed slot is
    lock-busy — liveness for housekeeping probes when the whole pool is
    registered. Extracted for direct unit-testing of the ordering invariant."""
    # `closed` slots have no live worker (RAM-ledger shed) — a borrow
    # would didChange a did_close'd URI. They are also unclaimed, so
    # without the filter they would be picked FIRST (external review
    # 2026-08-25: the third acquisition path the claim-site fix missed).
    return sorted((s for s in workers
                   if not getattr(s, "reserved", False)
                   and not getattr(s, "closed", False)),
                  key=lambda s: (s.claimed_by is not None, s.last_used_ts))


@contextlib.contextmanager
def _acquire_slot(meta: SessionMetadata, *, swap_in: bool = True,
                  borrow: bool = False):
    """Acquire a worker slot for one tool op.

    Two modes:

      Default (`borrow=False`) — for registered sessions only. The
      session has previously claimed a slot at `register_session`;
      this function locks the claimed slot for the duration of one
      tool op:
        * Hot path:  slot already has our content didChanged in
                     (`content_pipeline_id == pipeline_id`) → no swap.
        * Cold path: first tool call on this claim, or content was
                     cleared by a probe → didChange + set content_pipeline_id.

      Probe mode (`borrow=True`) — for one-shot RPCs that don't have a
      registered session (notably the framework's `/verify` endpoint).
      Borrows any free-lock slot, didChanges the probe's content in,
      and clears `content_pipeline_id` after release so the slot's
      registered owner re-loads its own content on its next acquire.
      Used sparingly; each borrow imposes one cold_warmup on the
      owner's subsequent acquire.

    `swap_in=False` skips the didChange — used by apply_edit which
    will overwrite content via its own RPC.
    """
    backend = _state.backend
    if backend is None:
        raise RuntimeError("backend not ready")
    if not _state.workers:
        raise RuntimeError("no workers in pool")

    if borrow:
        # Probe mode: find an unlocked slot via _borrow_order. The docstring
        # always promised "prefer unclaimed" but the code only implemented
        # "lock not held": a borrow could land on (and evict the warm content
        # of) a registered session's slot even while free slots sat idle —
        # and the plain-LRU order actively PREFERRED the slot of a pipeline
        # in a long think (oldest last_used_ts), the 2026-06-29 slot-thrash
        # shape. Claimed slots are now the fallback only when every unclaimed
        # slot is lock-busy (liveness: a housekeeping probe must still get a
        # slot when the whole pool is registered). Re-sort each poll so
        # claims/releases during the 120s window are observed.
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            for slot in _borrow_order(_state.workers):
                if slot.frozen:
                    continue    # no worker behind it — thaw's business
                if slot.lock.acquire(blocking=False):
                    try:
                        if swap_in:
                            with _elab_gate(slot.slot_uri, meta):
                                slot.file_version += 1
                                backend.clear_diagnostics(slot.slot_uri)
                                backend.did_change_full(
                                    slot.slot_path, meta.file_content,
                                    slot.file_version,
                                )
                                try:
                                    backend.wait_for_diagnostics(
                                        slot.slot_uri, slot.file_version,
                                        timeout=120,
                                    )
                                except (TimeoutError, RuntimeError):
                                    pass
                            # Probe owns content for the borrow only;
                            # clearing here forces the slot's registered
                            # owner (if any) to didChange its own
                            # content back in on its next acquire.
                            slot.content_pipeline_id = None
                            kind = "cold_warmup"
                            with _state.counters_lock:
                                _state.n_cold_warmup += 1
                        else:
                            kind = "cold_noswap"
                            with _state.counters_lock:
                                _state.n_cold_noswap += 1
                        yield (slot, kind)
                        slot.last_used_ts = time.time()
                        return
                    finally:
                        slot.lock.release()
            with _state.counters_lock:
                _state.n_busy_polls += 1
            time.sleep(0.1)
        raise RuntimeError(
            "no slot available for probe within 120s "
            "(all slots locked by their registered sessions' tool ops)"
        )

    # Claimed-session mode: locate this pipeline's claimed slot.
    my_slot: WorkerSlot | None = None
    for slot in _state.workers:
        if slot.claimed_by == meta.pipeline_id:
            my_slot = slot
            break
    if my_slot is None:
        # The claim is gone but the SESSION is not — an unregistered
        # token never reaches here (`no session`, :1659). The identity
        # and the resource are two layers, and only the resource was
        # destroyed: `_restart_backend` builds a whole fresh slot list,
        # so every live session's claim disappears with the old pool
        # while `_state.sessions` keeps every one of them. Re-claim is
        # what that function's own docstring has promised since it was
        # written ("their next tool call re-claims or gets a clear
        # error") — only the second half was ever implemented.
        #
        # Measured cost of the missing half: two death CLUSTERS, each
        # trailing a restart by minutes — 08-11 14:47:17Z → three deaths
        # 14:53/14:55/14:57, 08-12 06:06:43Z → two at 06:10/06:15. One
        # restart orphans every in-flight pipeline at once and they fall
        # over one by one as each next touches Lean.
        #
        # A session the stale-claim sweep took is `pop`ped from
        # `_state.sessions` outright (:844), so it cannot come back this
        # way — a reclaimed slot stays reclaimed.
        want_reserved = (meta.kind == "interactive")
        free: WorkerSlot | None = None
        with _state.sessions_lock:
            free = next((s for s in _state.workers
                         if s.claimed_by is None and not s.closed
                         and not s.frozen
                         and s.reserved == want_reserved), None)
            if free is not None:
                free.claimed_by = meta.pipeline_id
        if free is not None:
            # LOUD on purpose. Replacing the pool left no trace at all,
            # which is why this took two days and two clusters to find;
            # a self-healing path that swallows its own evidence just
            # moves the next investigation further from the cause.
            print(f"[gateway] pipeline {meta.pipeline_id[:8]} re-claimed "
                  f"slot {free.slot_id} — its previous claim is gone "
                  f"(backend restart replaces the whole pool). One cold "
                  f"warmup follows: the old slot's content died with the "
                  f"old backend.", file=sys.stderr, flush=True)
            my_slot = free

    if my_slot is None:
        # Everything else now has its own exit, so one cause is left:
        # the session is registered, the claim is gone, and there is no
        # free slot to give it. The two causes this message used to name
        # (register_session never called / release racing a use) were
        # wrong for every occurrence anyone investigated, and it sent
        # three separate investigations down the wrong path before
        # 2026-08-11; the sweep it then named was wrong for the two
        # clusters above. Third time: say only what is reachable.
        raise RuntimeError(
            f"no slot claimed for pipeline {meta.pipeline_id} and no free "
            f"slot to re-claim — every one of the {len(_state.workers)} "
            "worker slots is held by another session. This is a framework "
            "resource shortage, not anything in the file you are editing "
            "and nothing your patch can fix: retry this call, and if it "
            "repeats, report it as framework feedback."
        )

    deadline = time.monotonic() + 120.0
    _rewarm_wait_t0: "float | None" = None
    while time.monotonic() < deadline:
        if my_slot.lock.acquire(blocking=False):
            if my_slot.frozen:
                # No worker behind this slot — queue for the thaw (the
                # freeze contract: the wait is the framework's, credited
                # to the wall, bounded so a thaw that never comes errors
                # out loud instead of holding the session hostage).
                my_slot.thaw_waiting = True
                my_slot.lock.release()
                if _rewarm_wait_t0 is None:
                    _rewarm_wait_t0 = time.monotonic()
                elif time.monotonic() - _rewarm_wait_t0 \
                        > _FROZEN_WAIT_MAX_SEC:
                    _record_queue_credit(
                        meta, time.monotonic() - _rewarm_wait_t0)
                    raise RuntimeError(
                        "slot frozen under sustained RAM pressure for "
                        "30+ minutes — the machine cannot serve Lean "
                        "right now. Retry this call; if it repeats, "
                        "report it as framework feedback.")
                deadline = max(deadline, time.monotonic() + 120.0)
                with _state.counters_lock:
                    _state.n_busy_polls += 1
                time.sleep(0.5)
                continue
            if _rewarm_wait_t0 is not None:
                # The slot was mid-rewarm when this call arrived — the
                # queue time is the framework's, not the agent's (same
                # contract as the elab gate's credit).
                _record_queue_credit(
                    meta, time.monotonic() - _rewarm_wait_t0)
            try:
                if swap_in:
                    if my_slot.content_pipeline_id == meta.pipeline_id:
                        kind = "hot"
                        with _state.counters_lock:
                            _state.n_hot += 1
                    else:
                        # First tool call on this claim — slot is either
                        # in warmup state, carries a prior claim's
                        # stale content, or had its content cleared by a
                        # /verify probe borrow.
                        kind = "cold_warmup"
                        with _state.counters_lock:
                            _state.n_cold_warmup += 1
                        with _elab_gate(my_slot.slot_uri, meta):
                            my_slot.file_version += 1
                            backend.clear_diagnostics(my_slot.slot_uri)
                            merged, line_map = _compilation_for(meta)
                            backend.did_change_full(
                                my_slot.slot_path, merged,
                                my_slot.file_version,
                            )
                            try:
                                backend.wait_for_diagnostics(
                                    my_slot.slot_uri, my_slot.file_version,
                                    timeout=120,
                                )
                            except (TimeoutError, RuntimeError):
                                pass
                        my_slot.content_pipeline_id = meta.pipeline_id
                        my_slot.line_map = line_map
                else:
                    kind = "cold_noswap"
                    with _state.counters_lock:
                        _state.n_cold_noswap += 1
                meta.last_active = time.monotonic()
                yield (my_slot, kind)
                my_slot.last_used_ts = time.time()
                meta.last_active = time.monotonic()
                # The tool's result is computed and about to return —
                # the one provably-idle moment (owner design
                # 2026-08-26): weigh the worker, restart it in the
                # background if it grew far past the recycle line.
                _maybe_kick_midlease_rewarm(my_slot, meta)
                return
            finally:
                my_slot.lock.release()
        if my_slot.rewarming or my_slot.frozen:
            # A background rewarm/thaw holds the slot — slide the
            # deadline (both clear their flag in their own finally, and
            # the frozen branch above bounds the total wait) and start
            # the credit clock.
            if my_slot.frozen:
                my_slot.thaw_waiting = True
            if _rewarm_wait_t0 is None:
                _rewarm_wait_t0 = time.monotonic()
            deadline = max(deadline, time.monotonic() + 120.0)
        # Slot is locked by a concurrent tool op from this same pipeline
        # (single-threaded spawn ⇒ this should be rare and brief).
        with _state.counters_lock:
            _state.n_busy_polls += 1
        time.sleep(0.1)
    raise RuntimeError("claimed slot still busy after 120s")


# ─── Session ops ────────────────────────────────────

def _register_session_internal(
    pipeline_id: str, target_path: Path,
    problem: str, workspace: Path,
    log_path: Path | None,
    kind: str | None = None,
    interactive: bool = False,
    goal_id: "int | None" = None,
) -> tuple[str, str | None]:
    """Stash session metadata AND eagerly claim a worker slot
    (#118, 1:1 binding). The claim is registered by setting
    `slot.claimed_by`; the slot's `content_pipeline_id` stays at its
    prior value until the first tool call's didChange. NO didOpen here
    — that's lazy-deferred to first tool call. Returns (session_token,
    error). `interactive=True` claims ONLY a reserved slot (the serve
    UI's editor) and pipeline claims only unreserved ones — the
    pipeline=slot identity holds in both directions."""
    err = _ensure_backend_ready()
    if err:
        return "", err
    target_path = target_path.resolve()
    if not target_path.exists():
        return "", f"target file not found: {target_path}"
    content = target_path.read_text(encoding="utf-8")
    token = uuid.uuid4().hex
    meta = SessionMetadata(
        pipeline_id=pipeline_id,
        target_path=target_path,
        problem=problem,
        workspace=workspace.resolve(),
        log_path=log_path.resolve() if log_path else None,
        goal_id=goal_id,
        file_content=content,
        kind=kind,
    )
    # Claim a free worker slot for this session's lifetime. With
    # dispatch.pool == workers, there is always one free slot when a
    # spawn is dispatched (the dispatcher's ThreadPoolExecutor caps
    # in-flight spawns at pool size). If we still fail, that's a
    # dispatcher misconfiguration, not a runtime contention case.
    with _state.sessions_lock:
        free_slot = next(
            (s for s in _state.workers
             if s.claimed_by is None and not s.closed
             and not s.frozen
             and s.reserved == interactive), None,
        )
        if free_slot is None:
            return "", (
                "interactive slot busy — another editor session holds it"
                if interactive else
                "no free worker slot — pool exhausted "
                "(dispatch.pool must not exceed actual worker count)"
            )
        free_slot.claimed_by = pipeline_id
        _state.sessions[token] = meta
    _log_for(meta, {"event": "session_registered",
                    "pipeline_id": pipeline_id,
                    "claimed_slot": free_slot.slot_id,
                    "target": str(target_path)})
    return token, None


def _release_session_internal(token: str) -> None:
    """Drop session metadata and release this pipeline's claimed worker
    slot (1:1 lifecycle, #118). `content_pipeline_id` is left untouched
    — the next claim will didChange its own content in regardless, so
    clearing it eagerly buys nothing. Idempotent on unknown tokens."""
    freed: "WorkerSlot | None" = None
    with _state.sessions_lock:
        meta = _state.sessions.pop(token, None)
        if meta is None:
            return
        # Clear claim under sessions_lock so a concurrent register
        # cannot grab the slot before we release it.
        for slot in _state.workers:
            if slot.claimed_by == meta.pipeline_id:
                slot.claimed_by = None
                freed = slot
                break
    _log_for(meta, {"event": "session_released",
                    "pipeline_id": meta.pipeline_id})
    # OUTSIDE sessions_lock: the recycle re-warms a worker (tens of
    # seconds) and must not hold the lock every register waits on.
    # Ledger shed first: a slot the target no longer affords is CLOSED
    # (RAM back to the NL side) — recycling it would re-warm a worker
    # we are about to kill.
    if freed is not None:
        if freed.frozen:
            # No worker behind a frozen slot — nothing to shed or
            # recycle; the thaw loop reopens it (meta gone -> warmup).
            pass
        elif not _shed_slot_if_over_target(freed):
            _recycle_slot_if_heavy(freed)


def _current_session() -> SessionMetadata | None:
    token = _session_ctx.get()
    if token is None:
        return None
    with _state.sessions_lock:
        return _state.sessions.get(token)


# ─── Stale-claim sweep (#118 follow-up) ────────────────

# A silence threshold that no longer gates anything, kept for one job:
# it is the floor under `claim_ceiling_sec` (see `main`). The history is
# worth keeping because the constant got demoted twice, both times for
# the same reason.
#
# It began as the reclaim threshold, justified by "worker timeouts are
# 600s (main) + 180s (postmortem), so 900s is well above
# WORKER_TIMEOUT". Then `dispatch.spawn_timeout_sec` went 960 → 1800
# and the premise inverted — the TTL became HALF the life a worker is
# granted, and the sweep started taking slots from workers that were
# merely waiting on a heavy elaboration. Measured: 57 reclaims in one
# day, all in the 900-960s band, including pipeline d9c3e052 which went
# on issuing tool calls for another 20 minutes afterwards. Its next call
# got "no slot claimed", charged to the goal as a `lake_build_error` —
# infra death wearing mathematics' clothes. 2026-08-11 demoted it from
# "when to reclaim" to "when to start asking".
#
# 2026-08-13 removed the second role too. Silence is measured on the
# TOOL clock (`last_active`, updated in `_acquire_slot`), and a worker
# waiting on Lean is silent by definition — so silence was never
# evidence about the owner in either direction. Making it the
# PRECONDITION for asking meant a process that died at second one was
# not asked about until 900s, which is how a leak outlived the daemon
# that could have survived it. The question is cheap and the answer is
# on disk: `_sweep_stale_claims` now asks every pass.
_LEASE_TTL_SEC = 900.0
_SWEEP_INTERVAL_SEC = 60.0


def _owner_alive(meta: SessionMetadata) -> bool:
    """Is the process that claimed this slot still running?

    Same evidence as `state.recovery._attempt_owner_alive` (the
    `owner_pid` every SpawnWorkspace writes into its sandbox manifest)
    but the OPPOSITE default when the evidence is missing, and the
    difference is deliberate. There, unknown means "safe to delete an
    orphan directory", so unknown → dead. Here, unknown means "take a
    quarter of the pool away from something that may be working", so
    unknown → alive. Sessions with no attempts dir at all (the serve
    UI's editor, agy's LSP bridge) live in that gap.

    What keeps that default from becoming a leak is the ceiling in
    `_sweep_stale_claims`: an unknown owner holds its slot for at most
    `claim_ceiling_sec`, never forever.
    """
    try:
        import json as _json
        from ...agent.sandbox import MANIFEST_NAME, _pid_alive
        manifest_path = (Path(meta.workspace) / ".attempts"
                         / meta.pipeline_id / "sandbox" / MANIFEST_NAME)
        data = _json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return True         # no evidence — the ceiling bounds this
    try:
        return bool(_pid_alive(data.get("owner_pid")))
    except Exception:  # noqa: BLE001 — a probe must not halt the sweep
        return True


def _sweep_stale_claims() -> int:
    """One sweep pass: walk active sessions, reclaim any claim whose
    `last_active` is older than LEASE_TTL. Returns the count of slots
    reclaimed (0 in the steady-state hot path).

    Reclaim semantics match `_release_session_internal` — pop from
    `sessions` + clear `claimed_by` on the matching slot. We DO NOT
    clear `content_pipeline_id` (mirrors release semantics; the next
    claim's first tool call will didChange its own content in
    regardless).

    Brouwer 2026-05-23: observed 4/4 slots claimed but only 2 active
    spawn dirs on disk + workers_busy=0. /release urlopen failures
    silently leaked claims; the daemon eventually self-exited via
    CONSEC_GATEWAY_UNREACHABLE_LIMIT=8 once concurrent dispatches
    couldn't find any free slot.

    That last sentence used to end "Activity-TTL self-heals before that
    safety net trips." 2026-08-13 falsified it, and not narrowly: a
    killed daemon left 3 of 4 slots claimed, the next daemon REUSED the
    gateway (same code fingerprint, so the version-skew gate passed),
    every /register answered "no free worker slot", and the breaker
    fired at ~780s. The cure could not have raced the disease, because
    the cure was not running: the owner-liveness question was gated
    behind `_LEASE_TTL_SEC` of silence, so a process that had been dead
    since second one was not even ASKED about until 900s — and with its
    attempts dir already deleted by the next daemon's recovery sweep,
    the answer would have been "unknown → alive", holding the slot to
    the 3600s ceiling.

    So the gate is gone. Death is not a function of silence: ask every
    pass. Silence still governs the LIVE and UNKNOWN owners, via the
    ceiling — that part was always the point."""
    now = time.monotonic()
    reclaimed = 0
    with _state.sessions_lock:
        # Snapshot then mutate — we hold the lock for the whole sweep
        # because reclaim writes `claimed_by` and `sessions.pop` need
        # the same lock that /register / /release use to serialize
        # claim transitions. The work per session is O(workers) for
        # the slot lookup which is bounded (~4 in production), so
        # holding the lock for the full pass is cheap — and so is the
        # liveness probe (one small JSON read + one pid check), which
        # is why asking every pass costs nothing worth gating.
        for tok, meta in list(_state.sessions.items()):
            inactive_for = now - meta.last_active
            over_ceiling = inactive_for > _state.claim_ceiling_sec
            # Two independent grounds, neither derived from the other:
            #   * the owner is PROVABLY gone — reclaim now, at any age.
            #     A dead process will not issue another tool call, so
            #     there is nothing to protect and nothing to wait for.
            #   * the claim is past the absolute ceiling — reclaim
            #     regardless of liveness. A slot is 25% of the pool and
            #     an orphan (a daemon that died outside its Job Object)
            #     would otherwise hold one forever with nobody left to
            #     sweep it. A LIVE owner older than the spawn budget
            #     means the watchdog that should have killed it did
            #     not, and that is worth both the slot and a loud line.
            # An owner we cannot identify (the serve UI's editor, agy's
            # LSP bridge — no attempts dir at all) reads as alive by
            # `_owner_alive`'s deliberate default, so only the ceiling
            # ever takes its slot.
            owner_gone = not _owner_alive(meta)
            if not (owner_gone or over_ceiling):
                continue
            _state.sessions.pop(tok, None)
            for slot in _state.workers:
                if slot.claimed_by == meta.pipeline_id:
                    slot.claimed_by = None
                    break
            reclaimed += 1
            if over_ceiling:
                print(
                    f"[gateway] ANOMALY: reclaimed slot for pipeline "
                    f"{meta.pipeline_id[:8]} at {inactive_for:.0f}s "
                    f"inactive — past the {_state.claim_ceiling_sec:.0f}s "
                    f"ceiling, so the claim goes whether or not the owner "
                    f"still runs. An owner alive past its spawn budget "
                    f"means the watchdog did not fire; check it.",
                    file=sys.stderr, flush=True,
                )
            else:
                print(
                    f"[gateway] reclaimed leaked slot for "
                    f"pipeline {meta.pipeline_id[:8]} "
                    f"(owner pid is gone; it had been silent "
                    f"{inactive_for:.0f}s, which is NOT why — death is "
                    f"not a function of silence)",
                    file=sys.stderr, flush=True,
                )
    return reclaimed


def _stale_claim_sweep_loop() -> None:
    """Background daemon thread. Runs every `_SWEEP_INTERVAL_SEC`
    forever; any per-pass exception is logged and swallowed so a
    bad-state session can't crash the sweeper."""
    while True:
        try:
            time.sleep(_SWEEP_INTERVAL_SEC)
            _sweep_stale_claims()
        except Exception as exc:  # noqa: BLE001 — keep loop alive
            print(f"[gateway] stale-claim sweep raised: {exc}",
                  file=sys.stderr, flush=True)
