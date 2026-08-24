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
    assert rl.slot_gb_from_readings([1024, 1024]) == pytest.approx(1.0)
    # artifact filters: idle baseline below, recycle-capped above
    assert rl.slot_gb_from_readings([100]) == pytest.approx(0.6)
    assert rl.slot_gb_from_readings([9999]) == pytest.approx(1.6)


def test_nl_admit_floor_leaves_the_machine_its_share():
    """budget is a promise about the MACHINE: the floor is what the
    budget leaves to everyone else, plus the unit about to be spent."""
    floor = rl.nl_admit_floor_gb(28.0, 32.0, nl_gb=0.3)
    assert floor == pytest.approx(4.0 + 0.3 + 0.25)
    # budget == machine → only the unit + lag buffer remains
    assert rl.nl_admit_floor_gb(32.0, 32.0, nl_gb=0.3) == \
        pytest.approx(0.55)


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
    assert pushed["target"] == 24
    assert pushed["min_avail"] == pytest.approx(4.0)
    assert led.open_slots == 7 and led.free_slots == 3
    assert led.slot_gb == pytest.approx(1000 / 1024)


def test_ledger_tick_is_rate_limited(monkeypatch):
    led = rl.DispatcherLedger(28.0, 32.0)
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
