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
#: promise more than the calibrated working average. The ceiling holds
#: because the recycle policy (`gateway.slot_recycle_mb`, 1500 MB)
#: closes any idle slot past it — no steady state exists above.
_SLOT_GB_MIN, _SLOT_GB_MAX = SLOT_GB_FALLBACK, 1.6

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
                         slot_gb: float = SLOT_GB_FALLBACK,
                         nl_gb: float = NL_GB_FALLBACK,
                         margin_gb: "float | None" = None,
                         max_slots: int = MAX_SLOTS) -> int:
    """The pure target function. Idempotent — recompute from current
    demand any time; the floor() quantization IS the hysteresis band
    (NL demand must move ~slot_gb/nl_gb before the target moves one
    slot), so no event-delta counters exist to drift."""
    margin = slot_gb if margin_gb is None else margin_gb
    lean_ram = budget_gb - nl_demand * nl_gb - margin
    return max(1, min(max_slots, math.floor(lean_ram / slot_gb)))


def slot_gb_from_readings(readings_mb: "list[int | None]") -> float:
    """The measured slot coefficient: mean of the gateway's per-slot
    private-MB readings, clamped to sanity. Empty/unmeasured pool ->
    fallback."""
    vals = [mb for mb in readings_mb if mb]
    if not vals:
        return SLOT_GB_FALLBACK
    return max(_SLOT_GB_MIN, min(_SLOT_GB_MAX,
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


# ─── CPU axis: closed loop on the elaboration queue (2026-08-25) ────
#
# The RAM budget sized the Lean field for the machine's MEMORY; on the
# flagship (8 OCPU / 128 GB) the binding resource inverted: a 110 GB
# budget promised ~99 slots, ~93 concurrent sessions drove load to 41
# on 8 cores, 30s MCP handshakes starved, and the dispatcher's
# unclassified breaker halted the fleet. Idle warm slots cost ~0 CPU
# (measured: 100 slots, 0.30 cores) — SESSIONS cost, and only while
# elaborating.
#
# No open-loop coefficient (external review 2026-08-25: the load-41 /
# 93-session back-solve is not evidence — load average counts
# uninterruptible sleep, and sessions think off-CPU, so the session:
# lane ratio cannot be pinned from one spike). The control signal is
# the gateway's OWN congestion instrument: the elaboration-gate queue
# (`elab_waiting` / `elab_cap` in the /warm_target reply). AIMD:
# sustained waiters shrink the cap multiplicatively toward the lane
# count; a quiet queue grows it additively toward the RAM target. The
# session cap is legitimately ABOVE the lane count (thinking sessions
# don't hold a lane) — the loop finds each machine's own multiple.
CPU_CAP_START_FACTOR = 3          # first cap = lanes x this, then AIMD
CPU_CAP_SHRINK = 0.8              # multiplicative decrease
_CONGESTED_WAITERS = 2            # queue depth that counts as pressure
_SHRINK_AFTER_TICKS = 2           # sustained pressure, not one blip
_GROW_AFTER_TICKS = 8             # quiet ticks (~2 min) per +1


class DispatcherLedger:
    """Dispatcher-side ledger state + the rate-limited tick.

    The tick recomputes the slot target from live NL demand and live
    coefficients, pushes it to the gateway, and records the gateway's
    confirmed open/free counts — Lean admission gates on `open_slots`
    (never on the target itself), which keeps the /register
    "no free slot" contract intact while the pool converges."""

    PUSH_INTERVAL_SEC = 15.0
    #: A fresh spawn's RSS is invisible to the system counters for its
    #: first seconds; admissions younger than this hold a ledger-side
    #: credit so a tight pop loop cannot out-run the measurement
    #: (external review 2026-08-25, P1: burst over-admission).
    NL_CREDIT_SEC = 60.0

    def __init__(self, budget_gb: float, machine_gb: float) -> None:
        self.budget_gb = budget_gb
        self.machine_gb = machine_gb
        self.slot_gb = SLOT_GB_FALLBACK
        self.open_slots = 0
        self.free_slots = 0
        self.last_target = 0
        self._last_push = 0.0
        self._nl_admits: "list[float]" = []
        # CPU-axis AIMD state (2026-08-25): None until the gateway's
        # first reply carrying elab stats (older gateways report none —
        # the axis stays dormant, exactly like static mode).
        self.cpu_cap: "int | None" = None
        self._elab_lanes = 0
        self._pressure_ticks = 0
        self._quiet_ticks = 0

    def _cpu_cap_update(self, resp: "dict", ram_target: int) -> None:
        """AIMD on the gateway's elaboration-queue congestion."""
        try:
            lanes = int(resp.get("elab_cap") or 0)
            waiting = int(resp.get("elab_waiting") or 0)
        except (TypeError, ValueError):
            return
        if lanes <= 0:
            return
        self._elab_lanes = lanes
        if self.cpu_cap is None:
            self.cpu_cap = lanes * CPU_CAP_START_FACTOR
        if waiting >= _CONGESTED_WAITERS:
            self._pressure_ticks += 1
            self._quiet_ticks = 0
            if self._pressure_ticks >= _SHRINK_AFTER_TICKS:
                self._pressure_ticks = 0
                self.cpu_cap = max(lanes,
                                   math.floor(self.cpu_cap
                                              * CPU_CAP_SHRINK))
        elif waiting == 0:
            self._pressure_ticks = 0
            self._quiet_ticks += 1
            if (self._quiet_ticks >= _GROW_AFTER_TICKS
                    and self.cpu_cap < ram_target):
                self._quiet_ticks = 0
                self.cpu_cap += 1
        else:
            self._pressure_ticks = 0
            self._quiet_ticks = 0

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
                   + (nl_in_flight + self._pending_nl() + 1) * nl_gb)
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
        ram_target = compute_target_slots(
            budget_gb=self.budget_gb, nl_demand=nl_demand,
            slot_gb=self.slot_gb + nl_gb, nl_gb=nl_gb)
        # Each machine's binding axis decides (2026-08-25): RAM sizes
        # the field for memory, the CPU-axis AIMD for what the cores
        # are actually serving without congestion.
        target = ram_target if self.cpu_cap is None \
            else min(ram_target, self.cpu_cap)
        self.last_target = target
        resp = push(target, ABS_AVAILABLE_FLOOR_GB)
        if resp:
            try:
                self.open_slots = int(resp.get("open") or 0)
                self.free_slots = int(resp.get("free") or 0)
            except (TypeError, ValueError):
                pass
            readings = resp.get("slot_private_mb")
            if isinstance(readings, dict) and readings:
                self.slot_gb = slot_gb_from_readings(
                    list(readings.values()))
            self._cpu_cap_update(resp, ram_target)


def env_budget_spec(workspace=None) -> "str | None":
    """The configured budget spec (yaml `dispatch.ram_budget`, env
    `ASTERISM_RAM_BUDGET`). Import-cycle-safe accessor."""
    from . import config
    spec = config.get("dispatch.ram_budget", default="",
                      env_var="ASTERISM_RAM_BUDGET", workspace=workspace)
    return str(spec) if spec else None
