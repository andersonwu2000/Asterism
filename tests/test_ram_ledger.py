"""Adaptive RAM ledger (owner design 2026-08-25) — the split worker
economy: Lean slots follow target_slots(budget − NL reserve), NL kinds
admit on measured available RAM, NL has priority (a wake surge may
shrink the Lean field to its 1-slot floor; nothing claimed is revoked).
All coefficients are measured-with-fallback, never case-tuned: the
design is a general framework feature, not an Erdős fixture (owner
ruling)."""
from __future__ import annotations

import pytest

from Tooling.core import ram_ledger as rl
from Tooling.core.warmup import LEAN_QUEUE_KINDS, NL_QUEUE_KINDS


# ── budget parsing ──────────────────────────────────────────────

@pytest.mark.parametrize("spec,total,want", [
    ("28G", 32.0, 28.0),
    ("28GB", 32.0, 28.0),
    (" 85% ", 32.0, 27.2),
    ("120G", 128.0, 120.0),
    ("999G", 32.0, 32.0),        # clamps to the machine
    ("0G", 32.0, None),
    ("", 32.0, None),
    (None, 32.0, None),
    ("banana", 32.0, None),
])
def test_parse_budget(spec, total, want):
    got = rl.parse_budget(spec, total)
    if want is None:
        assert got is None
    else:
        assert got == pytest.approx(want)


# ── the target function ─────────────────────────────────────────

def test_target_slots_owner_worked_example():
    """The owner's 28 GB sketch, with the reserve corrected to imminent
    demand: 12 queued+in-flight NL at 0.3 GB → 6.6 GB reserve incl. the
    unconditional one-slot margin, ~21 GB of Lean field."""
    t = rl.compute_target_slots(budget_gb=28.0, nl_demand=12,
                                slot_gb=0.95, nl_gb=0.3,
                                machine_gb=32.0)
    # floor((28 - 3.6 - 0.95 - cache 2 - base 1) / 0.95) — the
    # four-term model: fixed base + per-slot + per-NL + file working
    # set, every byte in exactly one term (owner-accepted 2026-08-26);
    # reserves scale with the machine (the flagship constants shipped
    # unscaled strangled the 32 GB box to 3 slots, 2026-08-26)
    assert t == 21


def test_target_slots_floor_is_one_even_under_nl_flood():
    """Anti-starvation: an NL wake surge shrinks the field but never to
    zero — the Lean side keeps one slot no matter the demand."""
    t = rl.compute_target_slots(budget_gb=28.0, nl_demand=1000,
                                slot_gb=0.95, nl_gb=0.3)
    assert t == 1


def test_target_slots_ceiling_is_the_runaway_backstop():
    t = rl.compute_target_slots(budget_gb=10_000.0, nl_demand=0)
    assert t == rl.MAX_SLOTS


def test_target_quantization_is_the_hysteresis_band():
    """floor() IS the dead zone: NL demand must move ~slot/nl units
    before the target moves one slot — no event-delta counters to
    drift."""
    base = rl.compute_target_slots(budget_gb=28.0, nl_demand=14,
                                   slot_gb=0.95, nl_gb=0.3,
                                   machine_gb=32.0)
    assert rl.compute_target_slots(budget_gb=28.0, nl_demand=15,
                                   slot_gb=0.95, nl_gb=0.3,
                                   machine_gb=32.0) == base
    assert rl.compute_target_slots(budget_gb=28.0, nl_demand=18,
                                   slot_gb=0.95, nl_gb=0.3,
                                   machine_gb=32.0) < base


# ── measured coefficients ───────────────────────────────────────

def test_slot_gb_readings_mean_and_clamps():
    assert rl.slot_gb_from_readings([]) == rl.SLOT_GB_FALLBACK
    assert rl.slot_gb_from_readings([None, None]) == rl.SLOT_GB_FALLBACK
    assert rl.slot_gb_from_readings([1200, 1200]) == pytest.approx(
        1200 / 1024)
    # artifact filters: an idle-baseline pool must not PROMISE a bigger
    # field than the calibrated working average (the flagship's first
    # boot clamped to 0.6 and hit the MAX_SLOTS cap, 2026-08-25);
    # recycle-capped above.
    assert rl.slot_gb_from_readings([100]) == rl.SLOT_GB_FALLBACK
    # the ceiling IS the recycle threshold — one fact, one home (owner
    # ruling 2026-08-26): raising the recycle knob moves pricing with it
    assert rl.slot_gb_from_readings([9999]) == pytest.approx(
        rl.slot_recycle_gb())
    assert rl.slot_recycle_gb() == pytest.approx(
        rl.SLOT_RECYCLE_MB_DEFAULT / 1024)


def test_nl_admit_floor_is_absolute_not_machine_minus_budget():
    """The first cut used `machine - budget` and starved on the
    operator's own box: co-tenants were USING their share (available
    6.5 GB vs a 17.3 GB floor) and NL admission would never fire
    (2026-08-25). The floor is an absolute safety margin; the BUDGET
    bounds the ledger's own modeled footprint instead."""
    # machine-scaled since 2026-08-26 (the 1.5 GB absolute floor was
    # sized for a 32 GB box; on 125 GB the cache thrashed long before
    # it and strategists dispatched straight into the crush)
    assert rl.nl_admit_floor_gb(15.0, 32.0, nl_gb=0.3) == \
        pytest.approx(rl.pressure_low_gb(32.0) + 0.3)
    assert rl.nl_admit_floor_gb(110.0, 125.0, nl_gb=0.3) == \
        pytest.approx(0.06 * 125.0 + 0.3)
    # independent of how much of the machine the budget leaves
    assert rl.nl_admit_floor_gb(28.0, 32.0, nl_gb=0.3) == \
        rl.nl_admit_floor_gb(15.0, 32.0, nl_gb=0.3)


def test_nl_admission_is_bounded_by_the_modeled_footprint(monkeypatch):
    """Co-tenant RAM cannot starve us — but the budget still paces us:
    admission stops when open slots + NL spawns modeled at their
    coefficients would exceed the budget (the field width IS the token
    burn rate on paid seats — user 2026-08-25)."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.5)
    monkeypatch.setattr(rl, "available_gb", lambda: 20.0)
    led.open_slots = 12
    led.slot_gb = 1.0
    # modeled = 12*1.0 + (n+1)*0.5 + cache 2 + base 1 ≤ 28
    # → (n+1)*0.5 ≤ 13 → admits through n = 25 (equality admits)
    assert led.nl_admissible(25) is True
    assert led.nl_admissible(26) is False


def test_agent_proc_prefixes_cover_every_provider():
    """The NL coefficient is measured from the provider CLIs the llm
    layer actually spawns — a provider missing here silently degrades
    the measurement to the fallback constant (general-framework rule:
    coefficients are measured, not case-tuned)."""
    for prefix in ("claude", "codex", "agy"):
        assert prefix in rl.AGENT_PROC_PREFIXES


# ── DispatcherLedger ────────────────────────────────────────────

def _quiet_pressure(monkeypatch):
    """Pin the measured-pressure axes calm so tick tests stay about
    the model (the pressure feedback has its own tests)."""
    monkeypatch.setattr(rl, "framework_current_gb", lambda: None)
    monkeypatch.setattr(rl, "available_gb", lambda: 50.0)
    # the NL coefficient is a psutil walk over EVERY process on the box
    # (11s per tick with a fleet flying, 2026-08-29): pin it — tests that
    # want a specific value set it after this
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    # the opening-bid ramp (2026-08-29) starts at min(lanes, target):
    # pin lanes out of the way so model tests see the RAM formula
    # (the ramp has its own tests below)
    monkeypatch.setattr(rl, "elab_lanes", lambda: 10_000)
    # the CPU axis (2026-08-30) reads the live load average — under an
    # xdist run that can read hot; pin it to "unmeasurable" (abstains)
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: None)


def test_ledger_tick_pushes_and_ingests_the_reply(monkeypatch):
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    _quiet_pressure(monkeypatch)
    pushed = {}

    def push(target, min_avail):
        pushed["target"] = target
        pushed["min_avail"] = min_avail
        return {"open": 7, "free": 3,
                "slot_private_mb": {"0": 1100, "1": 900, "2": None}}

    led.tick(nl_demand=12, push=push)
    # Effective slot cost = worker heap + the Lean pipeline's own agent
    # CLI (external review 2026-08-25) — priced at the PESSIMISTIC seed
    # on a fresh ledger: floor((28 - 12*0.3 - cost) / cost) with
    # cost = recycle ceiling + 0.3.
    import math
    seed = rl.slot_recycle_gb()
    assert pushed["target"] == math.floor(
        (28.0 - 3.6 - (seed + 0.3) - rl.cache_reserve_gb(32.0)
         - rl.base_reserve_gb(32.0)) / (seed + 0.3))
    assert pushed["min_avail"] == pytest.approx(rl.ABS_AVAILABLE_FLOOR_GB)
    assert led.open_slots == 7 and led.free_slots == 3
    # EMA, not assignment: milliseconds after seeding, one reading must
    # barely move the price (the raw fleet mean rides the busy/idle mix)
    assert led.slot_gb == pytest.approx(seed, abs=0.01)
    assert led.slot_gb <= seed


def test_slot_price_seeds_pessimistic_and_measures_only_down(monkeypatch):
    """Owner ruling 2026-08-26: the optimistic 0.95 seed made every
    launch over-warm a pool it un-warmed 15 minutes later (local boot:
    target 14 -> 7, one 126s warm shed on arrival). The price starts at
    the recycle ceiling; measurements may only pull it down from
    there."""
    assert rl.DispatcherLedger(28.0, 32.0).slot_gb == pytest.approx(
        rl.slot_recycle_gb())
    # the default pricing of the pure function is the same worst case
    import math
    cost = rl.slot_recycle_gb() + rl.NL_GB_FALLBACK
    assert rl.compute_target_slots(budget_gb=110.0, nl_demand=0,
                                   machine_gb=125.0) == \
        math.floor((110.0 - cost - rl.cache_reserve_gb(125.0)
                    - rl.base_reserve_gb(125.0)) / cost)


def test_slot_price_is_an_ema_that_converges_when_aged(monkeypatch):
    """The same reading applied after a full time constant has elapsed
    lands on the measured mean — the window forgets, it does not pin."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    _quiet_pressure(monkeypatch)
    led._slot_gb_at -= led.SLOT_GB_EMA_TAU_SEC   # pretend hours passed
    led.tick(nl_demand=0, push=lambda t, f: {
        "open": 2, "free": 1, "slot_private_mb": {"0": 1100, "1": 900}})
    assert led.slot_gb == pytest.approx(1000 / 1024)


def test_all_none_readings_do_not_move_the_price(monkeypatch):
    """"Nothing measured" is not "the pool is thin" — an unmeasurable
    reply must not drag the price toward the fallback."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    _quiet_pressure(monkeypatch)
    led._slot_gb_at -= led.SLOT_GB_EMA_TAU_SEC
    before = led.slot_gb
    led.tick(nl_demand=0, push=lambda t, f: {
        "open": 2, "free": 1, "slot_private_mb": {"0": None, "1": None}})
    assert led.slot_gb == before


def test_nl_admission_debits_pending_credit(monkeypatch):
    """A tight pop loop must not out-run the RSS counters: every
    admission younger than the credit window debits available RAM at
    the NL coefficient (external review 2026-08-25, P1)."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "available_gb", lambda: 4.5)
    # floor = pressure_low(32)=3.5 + 0.3 = 3.8; headroom 0.7 → 3 admits
    assert led.nl_admissible(0) is True
    led.note_nl_admit()
    assert led.nl_admissible(1) is True
    led.note_nl_admit()
    assert led.nl_admissible(2) is True
    led.note_nl_admit()
    assert led.nl_admissible(3) is False, \
        "3 pending x 0.3 GB ate the 0.7 GB headroom"
    # credits expire once the RSS has had time to show up
    led._nl_admits = [t - led.NL_CREDIT_SEC - 1 for t in led._nl_admits]
    assert led.nl_admissible(3) is True


def test_target_is_ram_only_backpressure_owns_cpu(monkeypatch):
    """Owner 2026-08-26: the interim AIMD session cap is deleted — the
    warm pool is RAM's alone (cheap standby), and CPU is governed by
    the gateway's elaboration gate (tool calls queue; queue time is
    credited back to the wall). Elab stats in the reply must NOT clamp
    the pushed target."""
    led = rl.DispatcherLedger(110.0, 125.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    # the opening-bid ramp (2026-08-29) starts at min(lanes, target);
    # lanes is the test machine's core count, so pin it out of the way —
    # this test is about the REPLY's elab stats not clamping the target
    monkeypatch.setattr(rl, "elab_lanes", lambda: 10_000)
    _quiet_pressure(monkeypatch)
    for reply in ({"open": 0, "free": 0, "elab_cap": 6,
                   "elab_waiting": 0},
                  {"elab_cap": 6, "elab_waiting": 9},
                  {"elab_cap": 6, "elab_waiting": 9}):
        led._last_push = 0.0
        pushed = {}
        led.tick(nl_demand=0,
                 push=lambda t, f: (pushed.setdefault("t", t), reply)[1])
        # floor((110 - cost - cache) / cost) at the pessimistic seed —
        # congestion never shrinks it
        import math
        cost = rl.slot_recycle_gb() + 0.3
        assert pushed["t"] == math.floor(
            (110.0 - cost - rl.cache_reserve_gb(125.0)
             - rl.base_reserve_gb(125.0)) / cost)
    assert not hasattr(led, "cpu_cap")


def test_ledger_tick_is_rate_limited(monkeypatch):
    _quiet_pressure(monkeypatch)
    # Pinned clock, not a stretched interval: the 3600s stretch (the
    # 2026-08-25 flake guard) met uptime-anchored monotonic() on
    # freshly booted CI runners and suppressed the FIRST push — every
    # CI run red for 3 days (2026-08-25..28). A pinned clock kills
    # both races and pins first-tick-pushes besides.
    now = {"t": 100.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: now["t"])
    led = rl.DispatcherLedger(28.0, 32.0)
    led.PUSH_INTERVAL_SEC = 3600.0
    calls = []
    led.tick(nl_demand=0, push=lambda t, f: calls.append(t) or None)
    assert calls, "a fresh ledger's first tick must push, uptime be damned"
    now["t"] += 5.0
    led.tick(nl_demand=0, push=lambda t, f: calls.append(t) or None)
    assert len(calls) == 1, "second tick inside the interval must not push"


def test_ledger_unreachable_gateway_keeps_last_counts(monkeypatch):
    _quiet_pressure(monkeypatch)
    led = rl.DispatcherLedger(28.0, 32.0)
    led.open_slots = 9
    led.tick(nl_demand=0, push=lambda t, f: None)
    assert led.open_slots == 9


def test_nl_hard_cap_is_a_backstop_not_a_knob(monkeypatch):
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.2)
    assert rl.DispatcherLedger(28.0, 32.0).nl_hard_cap() == 96  # capped
    assert rl.DispatcherLedger(1.0, 32.0).nl_hard_cap() == 5


def test_cache_reserve_is_a_budget_tenant(monkeypatch):
    """The mmap'd olean set (1.8 GiB measured) is charged to OUR
    cgroup but belongs to no worker's private bytes — without a seat
    in the model, a swapless fleet evicts/refaults it in a loop (both
    2026-08-26 crushes). Env override for per-box tuning."""
    monkeypatch.delenv("ASTERISM_RAM_CACHE_RESERVE_GB", raising=False)
    monkeypatch.delenv("ASTERISM_RAM_BASE_RESERVE_GB", raising=False)
    # machine-scaled with floors: flagship census at 125 GiB, olean
    # floor on small boxes
    assert rl.cache_reserve_gb(125.0) == pytest.approx(5.0)
    assert rl.cache_reserve_gb(32.0) == pytest.approx(2.0)
    assert rl.base_reserve_gb(125.0) == pytest.approx(3.0)
    assert rl.base_reserve_gb(32.0) == pytest.approx(1.0)
    monkeypatch.setenv("ASTERISM_RAM_CACHE_RESERVE_GB", "4.0")
    assert rl.cache_reserve_gb(125.0) == 4.0, "env override is absolute"
    monkeypatch.setenv("ASTERISM_RAM_CACHE_RESERVE_GB", "banana")
    assert rl.cache_reserve_gb(32.0) == pytest.approx(2.0)


# ── measured-pressure feedback ──────────────────────────────────

def _tick(led, push=None):
    led._last_push = 0.0
    out = {}
    led.tick(nl_demand=0,
             push=push or (lambda t, f: (out.setdefault("t", t),
                                         None)[1]))
    return out.get("t")


def test_pressure_pauses_dispatch_but_leaves_the_target(monkeypatch):
    """The admission brake after the outlet redesign (owner design
    2026-08-27): hot pauses dispatch — and does NOTHING to the target.
    The old integrator (2 GB per hot tick, −1 per calm tick) wound up
    on release lag and oscillated the 32 GB co-tenant box (579 sheds /
    597 warms in 7 h); physical shrink now lives in the gateway's
    serialized outlet, one measured kill at a time."""
    led = rl.DispatcherLedger(110.0, 125.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "framework_current_gb", lambda: 105.0)
    monkeypatch.setattr(rl, "available_gb", lambda: 50.0)
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: None)
    t1 = _tick(led)
    assert led.dispatch_paused is True
    assert led.nl_admissible(0) is False, "paused must stop NL too"
    t2 = _tick(led)
    assert t2 == t1, "the ledger stops reinforcements; it no longer cuts"


def test_pressure_available_axis_trips_alone(monkeypatch):
    """Off-cgroup platforms (Windows local) keep the machine-scaled
    available watermark as their pressure signal."""
    led = rl.DispatcherLedger(110.0, 125.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "framework_current_gb", lambda: None)
    monkeypatch.setattr(rl, "available_gb",
                        lambda: rl.pressure_low_gb(125.0) - 1.0)
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: None)
    _tick(led)
    assert led.dispatch_paused is True


def test_pressure_hysteresis_holds_then_releases(monkeypatch):
    """Between the bands the state HOLDS (a 5 GB/min wave must not
    flap the pause); past the calm band the pause lifts."""
    led = rl.DispatcherLedger(110.0, 125.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "available_gb", lambda: 50.0)
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: None)
    cur = {"v": 105.0}
    monkeypatch.setattr(rl, "framework_current_gb", lambda: cur["v"])
    _tick(led)
    assert led.dispatch_paused is True
    cur["v"] = 100.0            # inside the band: 98 < 100 < 102
    _tick(led)
    assert led.dispatch_paused is True, "the band holds the pause"
    cur["v"] = 90.0             # calm: below 110 - 8 - 4
    _tick(led)
    assert led.dispatch_paused is False


# ───────────── CPU axis (owner ruling 2026-08-30) ─────────────
#
# Flagship 16 OCPU / 125 GB, 2026-08-30 00:00Z: the RAM axis read calm
# all night (the box has 125 GB), the ramp climbed to 31 slots, and the
# cores ran a queue of 69 (load 48-58 on 16). The pool's height is still
# RAM's to PLAN — but a second measured axis, the machine's run queue,
# now VETOES it exactly like RAM pressure does: hot pauses dispatch,
# calm resumes, the band between holds, and the ramp climbs only when
# BOTH axes are calm. Slots per core stay many-to-one: a thinking agent
# adds nothing to the load average, so only the slots that are actually
# elaborating count.

def _ram_calm(monkeypatch):
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "framework_current_gb", lambda: None)
    monkeypatch.setattr(rl, "available_gb", lambda: 50.0)


def test_cpu_load_ratio_is_loadavg_over_cores_and_abstains_when_unreadable(
        monkeypatch):
    import psutil
    monkeypatch.setattr(psutil, "getloadavg", lambda: (32.0, 20.0, 10.0))
    monkeypatch.setattr(rl._os, "cpu_count", lambda: 16)
    assert rl.cpu_load_ratio() == 2.0

    def boom():
        raise OSError("no loadavg here")
    monkeypatch.setattr(psutil, "getloadavg", boom)
    assert rl.cpu_load_ratio() is None


@pytest.mark.parametrize("ratio,paused", [
    (14 / 16, False),   # every elab lane busy, nothing queued: healthy
    (31 / 16, True),    # flagship 23:58Z
    (53 / 4, True),     # flagship 2026-08-29 (4 OCPU)
])
def test_cpu_axis_hot_pauses_dispatch_while_ram_is_calm(
        monkeypatch, ratio, paused):
    led = rl.DispatcherLedger(110.0, 125.0)
    _ram_calm(monkeypatch)
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: ratio)
    t1 = _tick(led)
    assert led.dispatch_paused is paused
    if paused:
        assert led.nl_admissible(0) is False, "paused must stop NL too"
        assert _tick(led) == t1, "the CPU axis stops reinforcements; it never cuts"


def test_cpu_axis_holds_between_bands_then_releases(monkeypatch):
    led = rl.DispatcherLedger(110.0, 125.0)
    _ram_calm(monkeypatch)
    ratio = {"v": 2.0}
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: ratio["v"])
    _tick(led)
    assert led.dispatch_paused is True
    ratio["v"] = 1.1            # inside the band: 1.0 < 1.1 < 1.25
    _tick(led)
    assert led.dispatch_paused is True, "the band holds the pause"
    ratio["v"] = 0.9            # calm
    _tick(led)
    assert led.dispatch_paused is False


def test_ramp_climbs_only_when_both_axes_are_calm(monkeypatch):
    """RAM calm and CPU merely not-hot is NOT calm: the ramp holds.
    (The 2026-08-30 climb to 31 slots happened on RAM's verdict alone.)"""
    _ram_calm(monkeypatch)
    monkeypatch.setattr(rl, "elab_lanes", lambda: 2)
    now = {"t": 100.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: now["t"])
    ratio = {"v": 1.1}
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: ratio["v"])
    led = rl.DispatcherLedger(110.0, 125.0)
    pushed = []
    push = lambda t, f: pushed.append(t) or None  # noqa: E731

    def tick_at(t):
        now["t"] = t
        led._last_push = -1e9
        led.tick(nl_demand=0, push=push)
    tick_at(100.0)
    assert pushed[-1] == 2, "opening bid"
    assert led.last_calm is False
    tick_at(170.0)
    assert pushed[-1] == 2, "CPU between bands: RAM's calm alone must not climb"
    ratio["v"] = 0.8
    tick_at(240.0)
    assert led.last_calm is True
    assert pushed[-1] == 3, ("both axes calm, a minute past the last "
                             "step: one step (the ramp's own rule)")


def test_build_headroom_is_measured_against_the_calm_watermark(monkeypatch):
    """A batch build is admitted only while the machine would STAY calm
    with its compiles on board: threads × per-compile GB must fit under
    available − the calm watermark (flagship 2026-08-30: 6.8 GB per
    `lean` compile, 108 of them, 4 GB left)."""
    monkeypatch.setattr(rl, "BUILD_GB_PER_THREAD", 7.0)
    monkeypatch.setattr(rl, "pressure_high_gb", lambda machine: 20.0)
    monkeypatch.setattr(rl, "available_gb", lambda: 50.0)
    assert rl.build_headroom_ok(4, machine_gb=125.0) is True    # 28 ≤ 30
    assert rl.build_headroom_ok(5, machine_gb=125.0) is False   # 35 > 30
    monkeypatch.setattr(rl, "available_gb", lambda: 21.0)
    assert rl.build_headroom_ok(1, machine_gb=125.0) is False, \
        "one compile would cross the watermark"


def test_cpu_axis_abstains_when_unmeasurable(monkeypatch):
    """No load average (the reading raised) → the CPU axis casts no
    vote: RAM's verdict stands alone, exactly the pre-2026-08-30 shape."""
    led = rl.DispatcherLedger(110.0, 125.0)
    _ram_calm(monkeypatch)
    monkeypatch.setattr(rl, "cpu_load_ratio", lambda: None)
    _tick(led)
    assert led.dispatch_paused is False
    assert led.last_calm is True


def test_nl_yield_demand_driven_priority(monkeypatch):
    """Owner ruling 2026-08-26 (forecast -> demand): a budget-blocked
    NL admission with free slots standing yields ONE slot per tick —
    re-requested while the block persists, decayed one per calm tick,
    never below the 1-slot floor."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    _quiet_pressure(monkeypatch)
    led.open_slots = 25
    led.slot_gb = 1.0
    # modeled = 25 + 0.3 + cache 2 + base 1 = 28.3 > 28 -> blocked,
    # and by the BUDGET branch
    assert led.nl_admissible(0) is False
    assert led.nl_blocked_by_budget is True
    led.request_nl_yield()
    t1 = _tick(led)
    led.request_nl_yield()
    t2 = _tick(led)
    assert t2 == t1 - 1, "each blocked tick yields one more slot"
    t3 = _tick(led)          # no request: the wave passed
    assert t3 == t2 + 1, "calm ticks give the yield back"


def test_nl_yield_only_answers_the_budget_branch(monkeypatch):
    """The hard cap and the measured floor are not yieldable — shedding
    a slot fixes neither, so they must not set the flag."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "available_gb", lambda: 1.0)  # under floor
    led.open_slots = 2
    led.slot_gb = 1.0
    assert led.nl_admissible(0) is False
    assert led.nl_blocked_by_budget is False


# ── partition + queue plumbing ──────────────────────────────────

def test_partition_has_no_overlap():
    assert set(LEAN_QUEUE_KINDS) & set(NL_QUEUE_KINDS) == set()


def test_queue_size_kind_filter(tmp_path, monkeypatch):
    from Tooling.state import db
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at,"
                 " bootstrap_done) VALUES ('p',?,1)", (db.now(),))
    conn.commit()
    for kind, n in (("Strategist", 3), ("Formalizer", 2)):
        for i in range(n):
            db.enqueue(conn, kind=kind, target_id=f"{kind}{i}",
                       problem="p", target_kind="Goal")
    assert db.queue_size(conn, kinds=NL_QUEUE_KINDS) == 3
    assert db.queue_size(conn, kinds=LEAN_QUEUE_KINDS) == 2
    assert db.queue_size(conn) == 5


# ───────────── opening-bid ramp (owner ruling 2026-08-29) ─────────────

def test_ramp_opens_at_min_of_lanes_and_ram_target(monkeypatch):
    """4 OCPU / 24 GB flagship, 2026-08-29: a per-worker constant opened
    9-11 slots onto 2 lanes (load 53, 6 frozen, 0 bricks). The pool now
    opens at min(lanes, RAM target) — lanes decide where the climb
    starts, RAM alone decides how high it goes."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "elab_lanes", lambda: 2)
    assert led._apply_ramp(12, now=100.0) == 2
    monkeypatch.setattr(rl, "elab_lanes", lambda: 14)
    led2 = rl.DispatcherLedger(110.0, 125.0)
    assert led2._apply_ramp(99, now=100.0) == 14
    led3 = rl.DispatcherLedger(28.0, 32.0)
    assert led3._apply_ramp(3, now=100.0) == 3, "lanes above target: RAM caps"


def test_ramp_climbs_one_slot_per_calm_minute_and_holds_when_not_calm(
        monkeypatch):
    monkeypatch.setattr(rl, "elab_lanes", lambda: 2)
    led = rl.DispatcherLedger(28.0, 32.0)
    assert led._apply_ramp(12, now=0.0) == 2
    led.last_calm = True
    assert led._apply_ramp(12, now=30.0) == 2, "half a minute: no step yet"
    assert led._apply_ramp(12, now=60.0) == 3
    assert led._apply_ramp(12, now=90.0) == 3
    assert led._apply_ramp(12, now=120.0) == 4
    led.last_calm = False
    assert led._apply_ramp(12, now=600.0) == 4, "not calm: hold"
    led.last_calm = True
    assert led._apply_ramp(12, now=660.0) == 5


def test_ramp_never_exceeds_and_follows_the_ram_target_down(monkeypatch):
    monkeypatch.setattr(rl, "elab_lanes", lambda: 6)
    led = rl.DispatcherLedger(28.0, 32.0)
    led.last_calm = True
    assert led._apply_ramp(7, now=0.0) == 6
    assert led._apply_ramp(7, now=60.0) == 7
    assert led._apply_ramp(7, now=120.0) == 7, "capped at the RAM target"
    assert led._apply_ramp(4, now=180.0) == 4, "target dropped: ramp follows"
    assert led._apply_ramp(7, now=240.0) == 5, "and climbs again from there"


def test_tick_pushes_the_ramped_target(monkeypatch):
    _quiet_pressure(monkeypatch)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    monkeypatch.setattr(rl, "elab_lanes", lambda: 2)
    now = {"t": 100.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: now["t"])
    led = rl.DispatcherLedger(110.0, 125.0)
    pushed = []
    led.tick(nl_demand=0, push=lambda t, f: pushed.append(t) or None)
    assert pushed == [2], "first push is the opening bid, not the RAM formula"


# ───────────── measured headroom clamp (owner ruling 2026-08-30) ─────────────

def test_target_is_clamped_by_measured_headroom_when_fat_slots_eat_the_budget(
        monkeypatch):
    """Two 8 GB workers plus a handful of fresh ones: the average-price
    formula still said 14, the machine sustained 7, and the outlet paid
    29 sheds to find that out. The ledger now also counts what the open
    slots actually hold: target ≤ open + headroom / price."""
    _quiet_pressure(monkeypatch)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    now = {"t": 100.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: now["t"])
    led = rl.DispatcherLedger(28.0, 32.0)
    led.slot_gb = 1.5
    pushed = []

    def push(target, min_avail):
        pushed.append(target)
        return {"open": 4, "free": 0,
                "slot_private_mb": {"0": 8000, "1": 8000, "2": 900, "3": 900}}
    led.tick(nl_demand=0, push=push)
    now["t"] += 60.0
    led.tick(nl_demand=0, push=push)
    # budget 28 − cache 2 − base 1 − used 17.4 = 7.6 GB headroom;
    # price ~1.5 → 5 more slots at most: 4 + 5 = 9, well under the
    # formula's answer
    assert pushed[-1] <= 9
    assert pushed[-1] >= 5


def test_headroom_clamp_never_starves_below_the_floor(monkeypatch):
    _quiet_pressure(monkeypatch)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    now = {"t": 100.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: now["t"])
    led = rl.DispatcherLedger(20.0, 32.0)
    led.slot_gb = 1.5
    pushed = []

    def push(target, min_avail):
        pushed.append(target)
        return {"open": 3, "free": 0,
                "slot_private_mb": {"0": 9000, "1": 9000, "2": 9000}}
    led.tick(nl_demand=0, push=push)
    now["t"] += 60.0
    led.tick(nl_demand=0, push=push)
    assert pushed[-1] >= 1, "the one-slot floor holds even when the slots overflow the budget"
