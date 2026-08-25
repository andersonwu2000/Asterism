"""core.ram_ledger — adaptive RAM ledger for the split worker economy.

Owner design (2026-08-25). The static `dispatch.pool` conflated two
resources that scale differently: a Lean worker slot costs ~0.95 GB of
private heap, an NL spawn (strategist wake, adversary round) costs
~0.15-0.2 GB of codex+node RSS and no Lean at all. On a free NL token
channel the pool cap was the only thing throttling the planning layer.

The ledger replaces the single number with a RAM budget:

    NL_reserve   = nl_gb x (queued NL wakes + in-flight NL) + margin
    target_slots = clamp(floor((budget - NL_reserve) / slot_gb),
                         1, MAX_SLOTS)

* NL demand counts QUEUED wakes, not all existing groups (owner ruling:
  a queued wake is imminent demand and its admission is what the
  reserve is for; a dormant group between wakes holds zero RAM).
* NL has PRIORITY over the Lean field (owner ruling): a wake surge may
  legitimately shrink target_slots — claimed slots are never revoked,
  the shrink lands at release time, and the floor of 1 slot is the only
  anti-starvation guarantee the Lean side keeps.
* The ledger PLANS; a measured veto DECIDES: every admission and every
  warm-up also checks the machine's actually-available RAM, so a
  co-tenant (the operator's browser, a stray build) squeezes the fleet
  instead of the fleet squeezing the machine. The veto floor is
  `total - budget + one unit` — the budget is a promise about how much
  of the MACHINE we may take, not a number private to the model.
* Coefficients are measured, not pinned: `slot_gb` follows the
  gateway's per-slot private-MB readings (the recycle policy's own
  instrument), `nl_gb` follows the RSS of live codex process trees.
  Calibration fallbacks (0.95 / 0.2, measured 2026-08-25 on the
  aarch64 fleet) apply when no reading is available.

`dispatch.ram_budget` unset -> the whole module is dormant and the
legacy static-pool semantics apply unchanged.
"""
from __future__ import annotations

import math
import re
import time

#: Absolute roster cap — a runaway-target backstop, far above any real
#: machine (128 slots ~ 125 GB of workers).
MAX_SLOTS = 128

#: Calibration fallbacks (2026-08-25): slot = the RAM-formula
#: coefficient (idle 0.6 GB, elaboration-weighted average ~0.95);
#: NL = codex ~105 MB + node wrapper ~46 MB + pipeline-thread WS.
SLOT_GB_FALLBACK = 0.95
NL_GB_FALLBACK = 0.2

#: Bounds for the measured slot coefficient — a reading outside these
#: is a measurement artifact, not a new truth about the library. The
#: FLOOR is the calibration average itself: a fresh pool reads its
#: idle baseline (~0.6 GB) and planning on that over-commits the
#: moment real work lands — the flagship's first boot clamped to 0.6
#: and inflated the target straight into the MAX_SLOTS cap
#: (2026-08-25). Measured values may only SHRINK the field, never
#: promise more than the calibrated working average. The CEILING is
#: the recycle threshold itself (`slot_recycle_gb`) — the framework's
#: own declaration of how fat a slot may get before its worker is
#: restarted, so pricing at it is the honest worst case and the two
#: knobs move together (owner ruling 2026-08-26; the previous
#: hand-pinned 1.6 was a second home for the same fact).
_SLOT_GB_MIN = SLOT_GB_FALLBACK

#: Default for `gateway.slot_recycle_mb` — the gateway imports THIS
#: value so the threshold and the price ceiling share one home.
SLOT_RECYCLE_MB_DEFAULT = 1500


def slot_recycle_gb() -> float:
    """The recycle threshold in GB — the ledger's pessimistic per-slot
    price ceiling. Reads the same config/env the gateway's recycle
    policy reads; a disabled recycle (<= 0) keeps the default so the
    ledger never prices a slot at zero."""
    mb = SLOT_RECYCLE_MB_DEFAULT
    try:
        from . import config as _cfg
        mb = int(_cfg.get("gateway.slot_recycle_mb",
                          default=SLOT_RECYCLE_MB_DEFAULT,
                          env_var="ASTERISM_SLOT_RECYCLE_MB", cast=int))
    except Exception:  # noqa: BLE001 — pricing must not halt a tick
        pass
    if mb <= 0:
        mb = SLOT_RECYCLE_MB_DEFAULT
    return mb / 1024.0

#: Page-cache reserve INSIDE the budget — the mmap'd olean set every
#: worker faults against (measured 1.8 GiB across 9,074 files,
#: 2026-08-26) plus workspace file pages. The ledger models PRIVATE
#: bytes, so without this line the model plans the cache's seats away;
#: those pages are charged to OUR cgroup, and once a cgroup limit (or
#: the machine) runs tight they are the only reclaimable thing in a
#: swapless fleet — the kernel evicts them, every worker refaults
#: them, and the loop eats all CPU (both 2026-08-26 flagship crushes).
OLEAN_CACHE_RESERVE_GB = 2.5


def cache_reserve_gb() -> float:
    """The budget's page-cache seat (env `ASTERISM_RAM_CACHE_RESERVE_GB`
    overrides the measured default)."""
    import os
    try:
        v = float(os.environ.get("ASTERISM_RAM_CACHE_RESERVE_GB", ""))
        if v >= 0:
            return v
    except ValueError:
        pass
    return OLEAN_CACHE_RESERVE_GB


_BUDGET_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(%|G|GB|GIB)?\s*$", re.IGNORECASE)


def parse_budget(spec: "str | None", total_gb: float) -> "float | None":
    """`"28G"` / `"85%"` -> GB; None/empty/unparseable -> None (legacy
    static-pool mode). A budget above the machine clamps to total."""
    if not spec:
        return None
    m = _BUDGET_RE.match(str(spec))
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "G").upper()
    gb = total_gb * val / 100.0 if unit == "%" else val
    if gb <= 0:
        return None
    return min(gb, total_gb)


def compute_target_slots(*, budget_gb: float, nl_demand: int,
                         slot_gb: "float | None" = None,
                         nl_gb: float = NL_GB_FALLBACK,
                         margin_gb: "float | None" = None,
                         cache_gb: "float | None" = None,
                         max_slots: int = MAX_SLOTS) -> int:
    """The pure target function. Idempotent — recompute from current
    demand any time; the floor() quantization IS the hysteresis band
    (NL demand must move ~slot_gb/nl_gb before the target moves one
    slot), so no event-delta counters exist to drift.

    No measurement in hand -> price PESSIMISTICALLY at the recycle
    ceiling plus the NL rider (owner ruling 2026-08-26): the optimistic
    fallback made every launch over-warm a pool it un-warmed 15 minutes
    later, one 126s cold warm-up at a time. Measurements may only grow
    the field back from here."""
    if slot_gb is None:
        slot_gb = slot_recycle_gb() + NL_GB_FALLBACK
    if cache_gb is None:
        cache_gb = cache_reserve_gb()
    margin = slot_gb if margin_gb is None else margin_gb
    lean_ram = budget_gb - nl_demand * nl_gb - margin - cache_gb
    return max(1, min(max_slots, math.floor(lean_ram / slot_gb)))


def slot_gb_from_readings(readings_mb: "list[int | None]") -> float:
    """The measured slot coefficient: mean of the gateway's per-slot
    private-MB readings, clamped to sanity. Empty/unmeasured pool ->
    fallback."""
    vals = [mb for mb in readings_mb if mb]
    if not vals:
        return SLOT_GB_FALLBACK
    ceiling = max(_SLOT_GB_MIN, slot_recycle_gb())
    return max(_SLOT_GB_MIN, min(ceiling,
                                 sum(vals) / len(vals) / 1024.0))


def total_gb() -> float:
    import psutil
    return psutil.virtual_memory().total / 2**30


def available_gb() -> float:
    import psutil
    return psutil.virtual_memory().available / 2**30


#: Absolute available-RAM floor — the last-ditch measured veto. The
#: first cut used `machine - budget` as the floor ("leave the rest to
#: others"), and on the operator's own 32GB box the others were USING
#: their share: available sat at 6.5 GB against a 17.3 GB floor and
#: NL admission would have starved forever (2026-08-25, first local
#: ledger run). Co-tenants spending their share must not block OUR
#: admission while the MODEL says we are inside budget — the budget
#: bounds the ledger's own usage model; the measured veto only stops
#: the machine from being squeezed to the edge.
ABS_AVAILABLE_FLOOR_GB = 1.5


def nl_admit_floor_gb(budget_gb: float, machine_gb: float,
                      nl_gb: float = NL_GB_FALLBACK) -> float:
    """The measured floor below which NL dispatch queues — an absolute
    machine-safety margin plus the unit about to be spent (see
    ABS_AVAILABLE_FLOOR_GB for why this is NOT `machine - budget`)."""
    return ABS_AVAILABLE_FLOOR_GB + nl_gb


#: Measured-NL-coefficient cache (a psutil process scan is not free;
#: NL RSS drifts slowly).
_NL_GB_CACHE: "dict" = {"at": 0.0, "val": NL_GB_FALLBACK}
_NL_GB_TTL = 30.0


#: Provider CLI process-name prefixes the llm layer spawns (tracks the
#: provider table in `llm.__init__`: claude / codex / antigravity-agy).
#: The NL coefficient is measured from THESE trees only — name+lineage
#: attribution, so the operator's own node processes (the serve UI, a
#: dev server) never pollute the reading. General across providers by
#: construction; a new provider adds its CLI name here (drift test
#: pins this against the provider table).
AGENT_PROC_PREFIXES: "tuple[str, ...]" = ("codex", "claude", "agy",
                                          "gemini")


def nl_gb_measured() -> float:
    """Mean RSS of live agent-CLI process trees (the CLI + a node
    parent when present). Fallback when none is alive."""
    now = time.monotonic()
    if now - _NL_GB_CACHE["at"] < _NL_GB_TTL:
        return _NL_GB_CACHE["val"]
    val = NL_GB_FALLBACK
    try:
        import psutil
        totals: "list[float]" = []
        for p in psutil.process_iter(["name", "memory_info", "ppid"]):
            try:
                name = (p.info["name"] or "").lower()
                if not name.startswith(AGENT_PROC_PREFIXES):
                    continue
                rss = p.info["memory_info"].rss
                try:
                    parent = p.parent()
                    if parent and (parent.name() or "").lower().startswith(
                            "node"):
                        rss += parent.memory_info().rss
                except (psutil.Error, OSError):
                    pass
                totals.append(rss / 2**30)
            except (psutil.Error, OSError, KeyError, TypeError):
                continue
        if totals:
            val = max(0.1, min(1.0, sum(totals) / len(totals)))
    except Exception:
        pass
    _NL_GB_CACHE["at"] = now
    _NL_GB_CACHE["val"] = val
    return val


# ─── CPU axis: pure backpressure, no admission (owner 2026-08-26) ───
#
# The ledger's CPU story ends at the gateway's elaboration gate. One
# mechanism per resource: RAM bounds the SESSION field (this module's
# target), CPU bounds CONCURRENT ELABORATIONS (the gateway's
# `_elab_gate` lanes — tool calls queue when the cores are busy, and
# the queue time is credited back to the session's wall). The interim
# AIMD session cap (2026-08-25) is deleted: it re-conflated the axes —
# clamping the WARM POOL to throttle CPU shrank a resource that was
# never scarce, paid a warm-up on every grow step, and guessed from
# history what the tool queue answers exactly, live, for free.


class DispatcherLedger:
    """Dispatcher-side ledger state + the rate-limited tick.

    The tick recomputes the slot target from live NL demand and live
    coefficients, pushes it to the gateway, and records the gateway's
    confirmed open/free counts — Lean admission gates on `open_slots`
    (never on the target itself), which keeps the /register
    "no free slot" contract intact while the pool converges."""

    PUSH_INTERVAL_SEC = 15.0
    #: Time constant for the slot-price EMA (owner call 2026-08-26,
    #: "幾小時的時間窗"): the instantaneous fleet mean rides the
    #: busy/idle mix (one slot reads 0.5 GB fresh and 3 GB
    #: mid-elaboration), and feeding that raw into the target turned
    #: composition noise into shed/warm churn. The price starts at the
    #: pessimistic ceiling and drifts toward the measured mean over
    #: hours; the clamp bounds it to [fallback, recycle ceiling]
    #: either way.
    SLOT_GB_EMA_TAU_SEC = 7200.0
    #: A fresh spawn's RSS is invisible to the system counters for its
    #: first seconds; admissions younger than this hold a ledger-side
    #: credit so a tight pop loop cannot out-run the measurement
    #: (external review 2026-08-25, P1: burst over-admission).
    NL_CREDIT_SEC = 60.0

    def __init__(self, budget_gb: float, machine_gb: float) -> None:
        self.budget_gb = budget_gb
        self.machine_gb = machine_gb
        # Pessimistic seed — the price only comes DOWN as measurements
        # arrive (see SLOT_GB_EMA_TAU_SEC).
        self.slot_gb = slot_recycle_gb()
        self.open_slots = 0
        self.free_slots = 0
        self.last_target = 0
        self._last_push = 0.0
        self._slot_gb_at = time.monotonic()
        self._nl_admits: "list[float]" = []

    def nl_hard_cap(self) -> int:
        """Absolute NL-parallelism backstop — what the budget could
        house if it held nothing but NL spawns. A runaway guard, not a
        tuning knob (the measured-RAM floor is the real brake)."""
        return max(4, min(96, int(self.budget_gb
                                  / max(0.05, nl_gb_measured()))))

    def note_nl_admit(self) -> None:
        """Record an NL admission — it debits the credit window until
        its RSS shows up in the system counters."""
        self._nl_admits.append(time.monotonic())

    def _pending_nl(self) -> int:
        cut = time.monotonic() - self.NL_CREDIT_SEC
        self._nl_admits = [t for t in self._nl_admits if t >= cut]
        return len(self._nl_admits)

    def nl_admissible(self, nl_in_flight: int) -> bool:
        """Admit while the LEDGER MODEL of our own footprint stays
        inside the budget (open slots at slot cost + NL spawns at NL
        cost + the one about to start), and the machine keeps its
        absolute safety margin. The budget bounds US; co-tenants
        spending their own share cannot starve admission (2026-08-25,
        first local run)."""
        if nl_in_flight >= self.nl_hard_cap():
            return False
        nl_gb = nl_gb_measured()
        modeled = (self.open_slots * self.slot_gb
                   + (nl_in_flight + self._pending_nl() + 1) * nl_gb
                   + cache_reserve_gb())
        if modeled > self.budget_gb:
            return False
        return (available_gb() - self._pending_nl() * nl_gb
                >= nl_admit_floor_gb(self.budget_gb, self.machine_gb,
                                     nl_gb))

    def tick(self, *, nl_demand: int, push) -> None:
        """Rate-limited recompute + push. `push(target, min_avail_gb)`
        -> the gateway's reply dict or None (unreachable: keep last
        known counts — the liveness gate owns that failure)."""
        now = time.monotonic()
        if now - self._last_push < self.PUSH_INTERVAL_SEC:
            return
        self._last_push = now
        nl_gb = nl_gb_measured()
        # A Lean pipeline runs an agent CLI of its own — the effective
        # per-slot cost is worker heap + that rider (the old static
        # formula's 0.6+0.35 split, both halves measured now; external
        # review 2026-08-25: the worker-only coefficient understated
        # the field and 26G was not a real fleet ceiling).
        # RAM alone sizes the field (owner 2026-08-26): the warm pool
        # is cheap standby, CPU is the elaboration gate's business.
        target = compute_target_slots(
            budget_gb=self.budget_gb, nl_demand=nl_demand,
            slot_gb=self.slot_gb + nl_gb, nl_gb=nl_gb)
        self.last_target = target
        resp = push(target, ABS_AVAILABLE_FLOOR_GB)
        if resp:
            try:
                self.open_slots = int(resp.get("open") or 0)
                self.free_slots = int(resp.get("free") or 0)
            except (TypeError, ValueError):
                pass
            readings = resp.get("slot_private_mb")
            # An all-None reading set is "nothing measured", not "the
            # pool is free" — it must not drag the price toward the
            # fallback.
            if isinstance(readings, dict) \
                    and any(v for v in readings.values()):
                measured = slot_gb_from_readings(list(readings.values()))
                dt = max(0.0, now - self._slot_gb_at)
                self._slot_gb_at = now
                alpha = min(1.0, dt / self.SLOT_GB_EMA_TAU_SEC)
                self.slot_gb += alpha * (measured - self.slot_gb)


def env_budget_spec(workspace=None) -> "str | None":
    """The configured budget spec (yaml `dispatch.ram_budget`, env
    `ASTERISM_RAM_BUDGET`). Import-cycle-safe accessor."""
    from . import config
    spec = config.get("dispatch.ram_budget", default="",
                      env_var="ASTERISM_RAM_BUDGET", workspace=workspace)
    return str(spec) if spec else None
