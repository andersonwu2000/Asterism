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
                                slot_gb=0.95, nl_gb=0.3)
    assert t == 24  # floor((28 - 3.6 - 0.95) / 0.95)


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
    base = rl.compute_target_slots(budget_gb=28.0, nl_demand=12,
                                   slot_gb=0.95, nl_gb=0.3)
    assert rl.compute_target_slots(budget_gb=28.0, nl_demand=13,
                                   slot_gb=0.95, nl_gb=0.3) == base
    assert rl.compute_target_slots(budget_gb=28.0, nl_demand=16,
                                   slot_gb=0.95, nl_gb=0.3) < base


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
    assert rl.nl_admit_floor_gb(15.0, 32.0, nl_gb=0.3) == \
        pytest.approx(rl.ABS_AVAILABLE_FLOOR_GB + 0.3)
    # independent of how much of the machine the budget leaves
    assert rl.nl_admit_floor_gb(28.0, 32.0, nl_gb=0.3) == \
        rl.nl_admit_floor_gb(15.0, 32.0, nl_gb=0.3)


def test_nl_admission_is_bounded_by_the_modeled_footprint(monkeypatch):
    """Co-tenant RAM cannot starve us — but the budget still paces us:
    admission stops when open slots + NL spawns modeled at their
    coefficients would exceed the budget (the field width IS the token
    burn rate on paid seats — user 2026-08-25)."""
    led = rl.DispatcherLedger(15.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.5)
    monkeypatch.setattr(rl, "available_gb", lambda: 20.0)
    led.open_slots = 12
    led.slot_gb = 1.0
    # modeled = 12*1.0 + (n+1)*0.5 ≤ 15 → admits through n = 5
    assert led.nl_admissible(5) is True
    assert led.nl_admissible(6) is False


def test_agent_proc_prefixes_cover_every_provider():
    """The NL coefficient is measured from the provider CLIs the llm
    layer actually spawns — a provider missing here silently degrades
    the measurement to the fallback constant (general-framework rule:
    coefficients are measured, not case-tuned)."""
    import inspect
    import Tooling.llm as llm
    src = inspect.getsource(llm)
    for provider, prefix in [("claude", "claude"), ("codex", "codex"),
                             ("antigravity", "agy")]:
        assert f'"{provider}"' in src, f"provider table lost {provider}?"
        assert prefix in rl.AGENT_PROC_PREFIXES


# ── DispatcherLedger ────────────────────────────────────────────

def test_ledger_tick_pushes_and_ingests_the_reply(monkeypatch):
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
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
        (28.0 - 3.6 - (seed + 0.3)) / (seed + 0.3))
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
    assert rl.compute_target_slots(budget_gb=110.0, nl_demand=0) == \
        math.floor((110.0 - cost) / cost)


def test_slot_price_is_an_ema_that_converges_when_aged(monkeypatch):
    """The same reading applied after a full time constant has elapsed
    lands on the measured mean — the window forgets, it does not pin."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
    led._slot_gb_at -= led.SLOT_GB_EMA_TAU_SEC   # pretend hours passed
    led.tick(nl_demand=0, push=lambda t, f: {
        "open": 2, "free": 1, "slot_private_mb": {"0": 1100, "1": 900}})
    assert led.slot_gb == pytest.approx(1000 / 1024)


def test_all_none_readings_do_not_move_the_price(monkeypatch):
    """"Nothing measured" is not "the pool is thin" — an unmeasurable
    reply must not drag the price toward the fallback."""
    led = rl.DispatcherLedger(28.0, 32.0)
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.3)
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
    monkeypatch.setattr(rl, "available_gb", lambda: 2.6)
    # floor = 1.5 + 0.3 = 1.8; headroom = 0.8 → 3 admits
    assert led.nl_admissible(0) is True
    led.note_nl_admit()
    assert led.nl_admissible(1) is True
    led.note_nl_admit()
    assert led.nl_admissible(2) is True
    led.note_nl_admit()
    assert led.nl_admissible(3) is False, \
        "3 pending x 0.3 GB ate the 0.8 GB headroom"
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
    for reply in ({"open": 0, "free": 0, "elab_cap": 6,
                   "elab_waiting": 0},
                  {"elab_cap": 6, "elab_waiting": 9},
                  {"elab_cap": 6, "elab_waiting": 9}):
        led._last_push = 0.0
        pushed = {}
        led.tick(nl_demand=0,
                 push=lambda t, f: (pushed.setdefault("t", t), reply)[1])
        # floor((110 - cost) / cost) at the pessimistic seed —
        # congestion never shrinks it
        import math
        cost = rl.slot_recycle_gb() + 0.3
        assert pushed["t"] == math.floor((110.0 - cost) / cost)
    assert not hasattr(led, "cpu_cap")


def test_ledger_tick_is_rate_limited(monkeypatch):
    led = rl.DispatcherLedger(28.0, 32.0)
    # A loaded parallel test run can stall >15s between the two calls
    # (measured flake, 2026-08-25) — the interval under test must not
    # race the wall clock.
    led.PUSH_INTERVAL_SEC = 3600.0
    calls = []
    led.tick(nl_demand=0, push=lambda t, f: calls.append(t) or None)
    led.tick(nl_demand=0, push=lambda t, f: calls.append(t) or None)
    assert len(calls) == 1, "second tick inside the interval must not push"


def test_ledger_unreachable_gateway_keeps_last_counts():
    led = rl.DispatcherLedger(28.0, 32.0)
    led.open_slots = 9
    led._last_push = 0.0
    led.tick(nl_demand=0, push=lambda t, f: None)
    assert led.open_slots == 9


def test_nl_hard_cap_is_a_backstop_not_a_knob(monkeypatch):
    monkeypatch.setattr(rl, "nl_gb_measured", lambda: 0.2)
    assert rl.DispatcherLedger(28.0, 32.0).nl_hard_cap() == 96  # capped
    assert rl.DispatcherLedger(1.0, 32.0).nl_hard_cap() == 5


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
