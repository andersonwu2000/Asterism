"""Gateway shared state — the worker-slot / session / process-global
dataclasses and the `_state` singleton every other module in this
package reads.

Split out of `gateway.py` 2026-08-29 (A1-1) unchanged. Everything here
is bound exactly once at import: importers may `from .state import
_state` without a stale-binding hazard, and the tests that patch
`gateway._state.<field>` reach this same object through the facade.

A1-4a added the two dependency-free leaves at the bottom: `_log_for`
(the per-session JSONL log) and `_ts_now` (the server-side stamp on tool
responses). Neither belongs to an axis of its own, both are consumed by
`rpc` and by the facade's `validate_file`, and every module already
imports this one — so putting them here is what let `sessions`' two
call-time `from . import _log_for` reach-backs close.
"""
from __future__ import annotations

import contextvars
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..client import LspClient


# ─── Worker slot ────────────────────────────────────────────────

WARMUP_CONTENT = "import Mathlib\n"


@dataclass
class WorkerSlot:
    """One persistent lean --worker holding a slot URI. Pre-warmed at
    startup with `import Mathlib`; subsequent loads are didChange swaps
    on this URI (~3-4s vs ~27s fresh worker).

    1:1 lifecycle (#118): each spawn claims one slot at register_session
    and holds it until release_session. `claimed_by` tracks ownership;
    `content_pipeline_id` tracks which pipeline's content is actually
    didChanged in (may lag `claimed_by` until the first tool call).
    """
    slot_id: int
    slot_path: Path
    slot_uri: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Lifetime ownership. None = available for claim. Set at
    # register_session, cleared at release_session.
    claimed_by: str | None = None
    # Reserved for the serve UI's interactive editor (owner's
    # pipeline=slot identity, both directions): pipeline claims skip
    # reserved slots, interactive claims take ONLY reserved slots, and
    # borrow probes never touch them.
    reserved: bool = False
    # Whose content is currently didChanged in this slot. May lag
    # `claimed_by` until the first tool call (warmup state has neither
    # set). Stale after release — next claim's first tool call rewrites.
    content_pipeline_id: str | None = None
    # Monotonic version for LSP didChange. Starts at 2 (didOpen was 1).
    file_version: int = 2
    # Wall-clock time of last release, kept for diagnostics.
    last_used_ts: float = 0.0
    # line_map of the compilation unit currently didChanged in (merged
    # line → session-content line, None for framework-prefix / sibling
    # region). Set whenever content is swapped in; tools translate their
    # positions / diagnostics through it. None until the first swap.
    line_map: "list[int | None] | None" = None
    # RAM-ledger lifecycle (2026-08-25): a closed slot keeps its roster
    # entry but has no live worker (did_close freed its RAM) and is
    # skipped by every claim. The warm-target converger re-opens it —
    # or extends the roster — when the target rises.
    closed: bool = False
    # Mid-lease rewarm (owner design 2026-08-26): a worker that grew
    # far past its content's own need DURING a lease is restarted in
    # the background right after a tool call returns (the agent is
    # thinking; the rebuild overlaps that window). True while the
    # background rewarm holds the slot; acquires slide their deadline
    # and the wait is credited to the session's wall.
    rewarming: bool = False
    # Freeze (owner design 2026-08-26, the fleet-level pressure
    # answer): over-budget -> the fattest idle worker is KILLED but
    # its session and claim survive; a tool call arriving meanwhile
    # queues on the slot (sliding deadline, wall credit — the CPU
    # gate's contract). When pressure clears, the thaw rebuilds the
    # worker from the session's own content and the queued call runs.
    # A suspend, not a kill: the cliff mechanisms stay as backstops.
    frozen: bool = False
    frozen_at: float = 0.0
    # Set while an acquire is queued on this frozen slot — the thaw
    # loop serves these sessions first.
    thaw_waiting: bool = False
    # Short cooldown stamp — bridges the reading cache's TTL right
    # after a rewarm (the stale fat reading must not re-trigger).
    rewarmed_at: float = 0.0
    # The content's OWN weight (owner insight 2026-08-26): fat that was
    # there the first time this content ran is the content's need; only
    # growth BEYOND it across later calls is residue worth a restart.
    # Measured at the first tool return after the content lands and
    # re-measured fresh after every rewarm; reset when the content
    # changes hands. Absolute thresholds judged the monster certs by
    # their (legitimate) size and churned — the delta cannot.
    content_baseline_mb: "int | None" = None
    baseline_for: "str | None" = None


# ─── Session metadata ────────────────────────────────────────

@dataclass
class SessionMetadata:
    """Per-pipeline state held in gateway. file_content is the mirror
    of the agent's accumulated edits; slot URIs are transient stages
    we push this content onto for elaboration. target_path is the
    real on-disk goal_lean — write-through ensures the framework's
    post-spawn cascade reads the agent's final state.

    `last_active` is the activity-TTL liveness signal: updated by
    `_acquire_slot` on every successful tool acquire and consumed by
    the `_sweep_stale_claims` background loop to reclaim leaked
    slots. Initialized to register-time so a fresh session that
    hasn't issued a tool call yet still gets the full LEASE_TTL grace
    window."""
    pipeline_id: str
    target_path: Path
    problem: str
    workspace: Path
    log_path: Path | None = None
    file_content: str = ""
    last_active: float = field(default_factory=time.monotonic)
    # Pipeline kind ('Backward' / 'Builder' / 'Forward' / …) — lets the
    # submission mirror give pipeline-ACCURATE verdicts (a non-proved
    # citation is a warn for a Backward decomposition but a hard commit
    # reject for Builder). Optional: an old client that doesn't send it
    # gets the kind-agnostic mirror, never an error.
    kind: str | None = None
    # Fingerprint of the attempts dir's `new_*.lean` stub set (name,
    # mtime_ns, size). A freshly WRITTEN stub changes the merged
    # compilation unit, but slot ownership never noticed — errors_at /
    # goal_at elaborated the PREVIOUS unit and reported phantom unknown
    # identifiers on citations validate_file accepted (agent_feedback
    # 2026-07-09/10, ~32 reports). `_resync_buffer_from_disk` compares
    # and invalidates the slot on change.
    stub_fingerprint: tuple = ()
    # The session's goal identity (register payload `goal_id`, threaded
    # from run_lsp_edit_loop 2026-08-26) — lets validate's parity probe
    # run the SAME strict-ancestor cycle predicate commit runs, so
    # "citation ok" can no longer precede a commit-time circularity
    # reject (feedback x2). Optional: older clients get no cycle check,
    # never an error.
    goal_id: "int | None" = None
    # --- heartbeat-budget gate (2026-08-12) -------------------------
    #: A heartbeat timeout has been reported to this agent at least once.
    hb_saw_timeout: bool = False
    #: The `maxHeartbeats` this session's content last asked for (None =
    #: never set it, i.e. Lean's default).
    hb_limit: "int | None" = None
    #: Wall seconds the last diagnostics call took — the number the gate
    #: quotes, because a machine-measured cost cannot drift the way a
    #: hard-coded "4M ≈ 8 minutes" would.
    hb_last_check_s: float = 0.0
    #: Content hashes already warned about: the SAME write resent is the
    #: confirmation, so the gate asks once and then gets out of the way.
    hb_confirmed: set = field(default_factory=set)


# ─── Gateway global state ─────────────────────────────────

@dataclass
class GatewayState:
    backend: LspClient | None = None
    workspace: Path | None = None
    workers: list[WorkerSlot] = field(default_factory=list)
    sessions: dict[str, SessionMetadata] = field(default_factory=dict)
    sessions_lock: threading.Lock = field(default_factory=threading.Lock)
    ready_event: threading.Event = field(default_factory=threading.Event)
    init_error: str | None = None
    # Slot acquire path counters (visible via /health). Under 1:1
    # binding (#118), cold_evicted never fires — slots are owned by a
    # single pipeline for their lifetime and never serve another's
    # content. Hot vs cold_warmup distinguishes first-tool-call (must
    # didChange) from later calls on the same claim.
    counters_lock: threading.Lock = field(default_factory=threading.Lock)
    n_hot: int = 0           # this slot already has our content loaded
    n_cold_warmup: int = 0   # first tool call on this slot for this claim
    n_cold_noswap: int = 0   # swap_in=False (apply_edit / validate_file)
    n_busy_polls: int = 0    # times we slept 0.1s waiting for our slot's lock
    # The dispatch.pool value this process launched under, BEFORE any
    # RAM clamp — the daemon's reuse gate compares yaml-to-yaml against
    # this, so a clamped pool doesn't read as a stale gateway.
    workers_configured: int | None = None
    # Absolute age past which a claim is reclaimed even from a LIVE
    # owner. Derived from `dispatch.spawn_timeout_sec` at startup (see
    # `_sweep_stale_claims`); the default matches a 1800s spawn.
    claim_ceiling_sec: float = 3600.0
    # One-way latch: the FIRST warm has finished (whatever happens to
    # the backend later). HTTP now opens before that warm, so this is
    # what separates "the pool has never been up" from "a wedge restart
    # cleared `ready_event` and Lean work is legitimately waiting for
    # the replacement". Lean surfaces refuse fast in the first case and
    # keep blocking in the second — `_ensure_backend_ready` alone can't
    # tell them apart, and blocking through the initial warm would put
    # a 240s wait on the event loop where `/compute` lives.
    first_warm_done: bool = False
    #: Set by the warm watcher when the initial warm fails; `main`
    #: turns it into the same rc 3 the blocking version exited with.
    warm_failed: str | None = None
    #: The uvicorn Server, so the watcher can ask it to stop rather
    #: than `os._exit` past the Lean-subtree reap in `main`'s finally.
    http_server: object | None = None
    #: Adaptive RAM ledger (owner design 2026-08-25). None = static
    #: mode: the pool is exactly what launch warmed, nothing closes.
    #: Set via POST /warm_target by the dispatcher's ledger tick; the
    #: converger warms toward it, the release path sheds above it.
    warm_target: "int | None" = None
    #: Measured veto the dispatcher sends with the target: never start
    #: a warm when the machine's available RAM (GB) is below this.
    warm_min_available_gb: float = 0.0
    #: The RAM budget (owner .env), stashed at launch for the freezer
    #: (owner design 2026-08-26): the gateway needs the same number the
    #: dispatcher's ledger plans with. None = no budget (freeze off).
    ram_budget_gb: "float | None" = None
    #: Single-flight latch for the background converger thread.
    warm_converger_on: bool = False


_state = GatewayState()

# Source-tree fingerprint at THIS process's import time (version-skew
# guard). The gateway deliberately outlives daemons; a reusing daemon
# compares this /health field against the CURRENT tree (lifecycle.
# code_fingerprint) and relaunches the gateway on any drift — a stale
# process answers /health 200 while its tool calls 500 on new-code
# requests (sphere daemon #5, 2026-07-05). Computed once: it must
# describe the code THIS process loaded, not the disk's later state.
from ..lifecycle import code_fingerprint as _code_fp
_CODE_FINGERPRINT = _code_fp()
del _code_fp
_session_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "asterism_session", default=None
)


# ─── Logging ─────────────────────────────────────────────

def _log_for(meta: SessionMetadata | None, event: dict) -> None:
    """Best-effort per-session JSONL log. Silent on missing log_path
    or any write failure — never crash a tool call over a log hiccup."""
    if meta is None or meta.log_path is None:
        return
    event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    try:
        meta.log_path.parent.mkdir(parents=True, exist_ok=True)
        with meta.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str))
            f.write("\n")
    except Exception:
        pass


def _ts_now() -> str:
    """High-precision UTC ISO timestamp for server-side stamping into
    tool responses. Pairs with claude.exe's session jsonl message
    timestamps to localize MCP transport / claude-internal latency
    versus actual gateway processing time. Cheap (<1µs)."""
    return datetime.now(timezone.utc).isoformat()
