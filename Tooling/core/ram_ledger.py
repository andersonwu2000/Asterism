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

* NL demand counts IN-FLIGHT spawns only (owner ruling 2026-08-26,
  superseding the 08-25 queued-wakes reserve): the queue length never
  predicts simultaneous NL (admission is paced), so the forecast was
  wrong in both directions — reserving seats for 25 wakes that never
  fly together, or zero while a wake is seconds away. Demand is
  OBSERVED instead: when an NL admission is blocked by the modeled
  budget while free slots exist, the tick yields one slot (shed the
  fattest free one) and the wake lands a tick later. Forecast stays
  where its criterion holds (the warm pool itself: provisioning
  latency ~150s is the expensive side there).
* NL has PRIORITY over the Lean field (owner ruling): the yield above
  IS that priority — claimed slots are never revoked, the shrink lands
  at shed/release time, and the floor of 1 slot is the only
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

#: File working set INSIDE the budget — the mmap'd olean set every
#: worker faults against (1.8 GiB across 9,074 files) plus workspace
#: file pages; the fleet's cgroup weighed file=5.1 GB under load
#: (census 2026-08-26). The ledger models PRIVATE bytes, so without
#: this line the model plans the cache's seats away; those pages are
#: charged to OUR cgroup, and once a cgroup limit (or the machine)
#: runs tight they are the only reclaimable thing in a swapless fleet
#: — the kernel evicts them, every worker refaults them, and the loop
#: eats all CPU (both 2026-08-26 flagship crushes).
#: Machine-scaled: the two calibration points are the 125.6 GiB
#: flagship census (file=5.1 GB under a 77-worker fleet) and the 32 GB
#: local box (olean 1.8 GiB + a small workspace set ≈ 2 GB). Shipping
#: the flagship constant unscaled strangled the local field to 3
#: slots (2026-08-26).
_CACHE_FLOOR_GB, _CACHE_FRACTION = 2.0, 0.04

#: The framework's own base footprint — daemon + gateway + shim +
#: serve pythons (1.2 GB) and kernel slab (1.3 GB), measured on the
#: 125.6 GiB flagship under load; both shrink with fleet size, so the
#: seat is machine-scaled with a floor. The four-term model (fixed
#: base + per-slot marginal + per-NL marginal + file working set)
#: keeps every byte in exactly one term.
_BASE_FLOOR_GB, _BASE_FRACTION = 1.0, 0.024


def base_reserve_gb(machine_gb: "float | None" = None) -> float:
    """The fixed-base seat (env `ASTERISM_RAM_BASE_RESERVE_GB`
    overrides with an absolute value)."""
    import os
    try:
        v = float(os.environ.get("ASTERISM_RAM_BASE_RESERVE_GB", ""))
        if v >= 0:
            return v
    except ValueError:
        pass
    m = total_gb() if machine_gb is None else machine_gb
    return max(_BASE_FLOOR_GB, _BASE_FRACTION * m)


def cache_reserve_gb(machine_gb: "float | None" = None) -> float:
    """The budget's page-cache seat (env `ASTERISM_RAM_CACHE_RESERVE_GB`
    overrides with an absolute value)."""
    import os
    try:
        v = float(os.environ.get("ASTERISM_RAM_CACHE_RESERVE_GB", ""))
        if v >= 0:
            return v
    except ValueError:
        pass
    m = total_gb() if machine_gb is None else machine_gb
    return max(_CACHE_FLOOR_GB, _CACHE_FRACTION * m)


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
                         machine_gb: "float | None" = None,
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
        cache_gb = cache_reserve_gb(machine_gb)
    margin = slot_gb if margin_gb is None else margin_gb
    lean_ram = (budget_gb - nl_demand * nl_gb - margin - cache_gb
                - base_reserve_gb(machine_gb))
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


def pressure_low_gb(machine_gb: float) -> float:
    """Below this measured available-RAM line the fleet is squeezing
    the machine — dispatch pauses and the gateway's pressure outlet
    starts its measured kills. Machine-scaled (owner-confirmed hole,
    2026-08-26): the old absolute 1.5 GB floor was sized for a 32 GB
    co-tenant box; on 125 GB the page cache thrashes long before it,
    so strategists kept dispatching straight into the crush."""
    return max(ABS_AVAILABLE_FLOOR_GB + 2.0, 0.06 * machine_gb)


def pressure_high_gb(machine_gb: float) -> float:
    """Above this line the pause lifts and the outlet forgives debt,
    one measured step at a time — the gap to `pressure_low_gb` is the
    hysteresis band that keeps a 5 GB/min inflation wave (measured)
    from oscillating the feedback."""
    return pressure_low_gb(machine_gb) + 4.0


def _cgroup_footprint_gb(cg_dir: str) -> "float | None":
    """`memory.current` MINUS the cgroup's file pages — the framework's
    unreclaimable footprint (anon heap + page tables + slab + shmem).

    `memory.current` alone charges every page-cache page the unit ever
    touched: on 2026-08-29 a fresh 4-OCPU/24 GB flagship daemon read
    11.4 GB of which 8.6 GB were file pages (6.0 GB the workers' mmapped
    .olean, shared and reclaimable) against 2.0 GB anon. The cgroup axis
    (hot above budget-8, calm below budget-12) could then never go calm
    on a 19 GB budget — dispatch stayed PAUSED and the outlet shed the
    pool down to one worker while `available` sat at 20 GB. File pages
    are the kernel's to reclaim (the olean map is the one thing the
    no-swap fleet can drop); they are not pressure. `memory.stat` missing
    → the raw reading (the pre-fix, conservative shape); either file
    missing → None."""
    try:
        with open(f"{cg_dir}/memory.current", "r", encoding="utf-8") as fh:
            current = int(fh.read().strip())
    except (OSError, ValueError):
        return None
    file_bytes = 0
    try:
        with open(f"{cg_dir}/memory.stat", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) == 2 and parts[0] == "file":
                    file_bytes = int(parts[1])
                    break
    except (OSError, ValueError):
        file_bytes = 0
    return max(0, current - file_bytes) / 2**30


def framework_current_gb() -> "float | None":
    """The daemon unit cgroup's unreclaimable footprint in GB (see
    `_cgroup_footprint_gb`): the honest side of every model-vs-reality
    gap (the 2026-08-26 census that found the model saying 110 while
    the cgroup weighed 117.5 was this reading, cache included — the
    cache term is now excluded, 2026-08-29). None off-Linux or outside
    a cgroup (Windows local: the modeled footprint + available floor
    remain the only guards)."""
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as fh:
            first = fh.read().strip().splitlines()[0]
        rel = first.split("::", 1)[1] if "::" in first else ""
        if not rel:
            return None
    except (OSError, ValueError, IndexError):
        return None
    return _cgroup_footprint_gb(f"/sys/fs/cgroup{rel}")


def nl_admit_floor_gb(budget_gb: float, machine_gb: float,
                      nl_gb: float = NL_GB_FALLBACK) -> float:
    """The measured floor below which NL dispatch queues — the
    machine-scaled pressure line plus the unit about to be spent
    (same signal the dispatch pause and the pressure outlet consume; see
    ABS_AVAILABLE_FLOOR_GB for why this is NOT `machine - budget`)."""
    return pressure_low_gb(machine_gb) + nl_gb


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
AGENT_PROC_PREFIXES: "tuple[str, ...]" = ("codex", "claude", "agy")


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


def elab_lanes() -> int:
    """The gateway's elaboration lane count (same formula as
    `lsp/gateway/elab.py`, env override included) — the ledger's OPENING
    bid for the warm pool, never its ceiling (owner ruling 2026-08-29):
    RAM alone decides how high the pool climbs; the lanes only decide
    where the climb starts, so a 4-core box does not open 12 sessions
    onto 2 lanes at boot."""
    import os as _os
    env = _os.environ.get("ASTERISM_LEAN_ELAB_CONCURRENCY")
    try:
        if env and int(env) > 0:
            return int(env)
    except ValueError:
        pass
    return max(2, (_os.cpu_count() or 4) - 2)


class DispatcherLedger:
    """Dispatcher-side ledger state + the rate-limited tick.

    The tick recomputes the slot target from live NL demand and live
    coefficients, pushes it to the gateway, and records the gateway's
    confirmed open/free counts — Lean admission gates on `open_slots`
    (never on the target itself), which keeps the /register
    "no free slot" contract intact while the pool converges."""

    PUSH_INTERVAL_SEC = 15.0
    #: Measured-growth ramp (owner ruling 2026-08-29): the pool opens at
    #: min(elab lanes, RAM target) and climbs ONE slot per calm interval
    #: — calm being the pressure band's own verdict — up to the RAM
    #: target. Shrinking is the outlet's/freezer's business, as before.
    #: The 2026-08-29 flagship boot (4 OCPU / 24 GB) opened 9-11 slots
    #: from a per-worker constant the field then measured at 2.5-2.9 GB:
    #: load 53, 6 frozen slots, 0 bricks. No constant survives here.
    RAMP_STEP_SEC = 60.0
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
    #: Pause dispatch when the cgroup's true footprint climbs within
    #: this headroom of the budget — at the measured 5.4 GB/min
    #: inflation rate (per-worker heap 0.45 -> 2.2 GB per elaboration
    #: pass, 6 lanes) 8 GB buys the pause 90+ seconds of lead.
    PRESSURE_HEADROOM_GB = 8.0
    #: Extra calm required before the pause lifts / debt forgives
    #: (hysteresis on the cgroup axis; the available axis has its own
    #: band in pressure_low/high_gb).
    PRESSURE_RELEASE_SLACK_GB = 4.0

    def __init__(self, budget_gb: float, machine_gb: float) -> None:
        self.budget_gb = budget_gb
        self.machine_gb = machine_gb
        # Pessimistic seed — the price only comes DOWN as measurements
        # arrive (see SLOT_GB_EMA_TAU_SEC).
        self.slot_gb = slot_recycle_gb()
        self.open_slots = 0
        self.free_slots = 0
        self.last_target = 0
        self._ramp: "int | None" = None
        self._ramp_at = 0.0
        self.last_calm = False
        self.last_hot = False
        # -inf, not 0.0: monotonic() is uptime-anchored, so on a young
        # machine 0.0 is INSIDE the interval and the first push gets
        # suppressed — CI runners boot minutes before the suite and sat
        # red on exactly this for 3 days (2026-08-25..28).
        self._last_push = -math.inf
        self._slot_gb_at = time.monotonic()
        self._nl_admits: "list[float]" = []
        #: Measured-pressure feedback (owner-approved 2026-08-26): the
        #: model PLANS the target, the measured axes VETO it. `paused`
        #: stops ALL dispatch; the cut trims the pushed target so
        #: releases shed instead of re-claiming.
        self.dispatch_paused = False
        #: Demand-driven NL yield (owner design 2026-08-26): grows one
        #: slot per tick while an NL admission is budget-blocked with
        #: free slots standing, decays one per calm tick. The pushed
        #: target carries it, the converger sheds the fattest free
        #: slot, the wake lands a tick later.
        self._nl_yield = 0
        self._nl_yield_req = False
        #: Set by nl_admissible: the last refusal was the modeled
        #: budget (yieldable), not the hard cap / measured floor.
        self.nl_blocked_by_budget = False

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
        self.nl_blocked_by_budget = False
        if self.dispatch_paused:
            return False
        if nl_in_flight >= self.nl_hard_cap():
            return False
        nl_gb = nl_gb_measured()
        modeled = (self.open_slots * self.slot_gb
                   + (nl_in_flight + self._pending_nl() + 1) * nl_gb
                   + cache_reserve_gb(self.machine_gb)
                   + base_reserve_gb(self.machine_gb))
        if modeled > self.budget_gb:
            # The one refusal a slot yield can fix (demand-driven
            # priority, owner design 2026-08-26).
            self.nl_blocked_by_budget = True
            return False
        return (available_gb() - self._pending_nl() * nl_gb
                >= nl_admit_floor_gb(self.budget_gb, self.machine_gb,
                                     nl_gb))

    def _apply_pressure(self, target: int) -> int:
        """Measured admission brake — hot pauses dispatch, calm resumes
        it, the band between holds (hysteresis). Two live axes, either
        one trips: the unit cgroup's true footprint against the budget,
        and the machine's available RAM against the scaled watermark.

        This USED to also trim the target ~2 GB per hot tick with a
        1-per-calm-tick drain — an open-loop integrator that wound up
        on a shared 32 GB desktop (27 pause/clear cycles, 579 sheds /
        597 warms in 7 h, measured 2026-08-27): release lags kept the
        hot reading true for several ticks, each added another step,
        and the residue carried into the next episode. Physical shrink
        now lives in the gateway's serialized pressure outlet (owner
        design 2026-08-27: one measured kill at a time, the previous
        death confirmed before the next reading decides) — the ledger
        only stops reinforcements."""
        cur = framework_current_gb()
        avail = available_gb()
        hot = ((cur is not None
                and cur > self.budget_gb - self.PRESSURE_HEADROOM_GB)
               or avail < pressure_low_gb(self.machine_gb))
        calm = ((cur is None
                 or cur < (self.budget_gb - self.PRESSURE_HEADROOM_GB
                           - self.PRESSURE_RELEASE_SLACK_GB))
                and avail > pressure_high_gb(self.machine_gb))
        self.last_hot, self.last_calm = bool(hot), bool(calm)
        if hot:
            if not self.dispatch_paused:
                cur_s = "n/a" if cur is None else f"{cur:.1f}G"
                print(f"[ledger] measured pressure — dispatch PAUSED "
                      f"(cgroup {cur_s} vs budget {self.budget_gb:.0f}G, "
                      f"available {avail:.1f}G); the gateway outlet "
                      f"sheds one measured kill at a time", flush=True)
            self.dispatch_paused = True
        elif calm:
            if self.dispatch_paused:
                print(f"[ledger] pressure cleared — dispatch resumes "
                      f"(available {avail:.1f}G)", flush=True)
            self.dispatch_paused = False
        # between the bands: hold state (hysteresis)
        return target

    def request_nl_yield(self) -> None:
        """Dispatcher-side signal: an NL admission is blocked by the
        modeled budget while free slots stand — yield one. Consumed by
        the next tick; must be re-requested while the block persists
        (a passed wave decays the yield one slot per tick)."""
        self._nl_yield_req = True

    def _apply_ramp(self, target: int, now: float) -> int:
        """Opening bid = min(lanes, target); +1 per calm RAMP_STEP_SEC;
        never above the RAM target, and follows it down."""
        target = max(1, int(target))
        if self._ramp is None:
            self._ramp = max(1, min(elab_lanes(), target))
            self._ramp_at = now
            print(f"[ledger] warm pool opens at {self._ramp} (lanes "
                  f"{elab_lanes()}, RAM target {target}) and climbs one "
                  f"slot per calm minute", flush=True)
        elif (self.last_calm and self._ramp < target
              and now - self._ramp_at >= self.RAMP_STEP_SEC):
            self._ramp += 1
            self._ramp_at = now
        self._ramp = min(self._ramp, target)
        return self._ramp

    def _apply_nl_yield(self, target: int) -> int:
        if self._nl_yield_req:
            self._nl_yield_req = False
            if self._nl_yield < max(0, target - 1):
                self._nl_yield += 1
                print(f"[ledger] NL yield — a queued wake is budget-"
                      f"blocked with free slots standing; target gives "
                      f"up {self._nl_yield} slot(s) (the fattest free "
                      f"one sheds)", flush=True)
        elif self._nl_yield > 0:
            self._nl_yield -= 1
        return max(1, target - self._nl_yield)

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
            slot_gb=self.slot_gb + nl_gb, nl_gb=nl_gb,
            machine_gb=self.machine_gb)
        target = self._apply_pressure(target)
        # ramp first, yield last: the ramp climbs toward (and follows
        # down) the RAM target; the NL yield is a transient shed on top
        # of the pool and must not reset the climb (its decay is one
        # slot per calm TICK, the ramp's step one per calm MINUTE)
        target = self._apply_ramp(target, now)
        target = self._apply_nl_yield(target)
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
