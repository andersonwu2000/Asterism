"""Kernel-certified disproof gate (owner design 2026-08-25).

A bare `-- decline: unprovable` flipped the TRUE kelly_core to
`disproved` (hard terminal + dedupe #112a poison) on the agent's
say-so — the intake channel demanded a counterexample, the work-turn
channel demanded nothing (sylvester_gallai, 2026-08-24). Now the ONLY
road to disproved is a submission that PROVES the negation, certified
in the kernel by the absurd-bridge probe."""
import sqlite3
from pathlib import Path

import pytest

import Tooling.pipeline as pipeline
from Tooling.pipeline import _disprove


PATCH = """import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- decline: disprove
theorem kelly_core (p : Nat) : False := by
  trivial

end Problems.sylvester_gallai
"""


def test_bare_unprovable_no_longer_reaches_disproved() -> None:
    assert (pipeline.DECLINE_TO_FAILURE_REASON[pipeline.DECLINE_UNPROVABLE]
            == "agent_declined")
    assert "agent_infeasible" not in pipeline.DECLINE_TO_FAILURE_REASON.values()
    assert pipeline.DECLINE_DISPROVE in pipeline.DECLINE_DIRECTIVES
    assert pipeline.DECLINE_DISPROVE not in pipeline.DECLINE_TO_FAILURE_REASON


def test_build_probe_renames_imports_and_bridges() -> None:
    probe = _disprove.build_probe(
        PATCH, slug="kelly_core",
        goal_lean_path="Problems/sylvester_gallai/proofs/L_kelly_core.lean")
    assert "theorem kelly_core_disproof_claim (p : Nat)" in probe
    # original head is gone; imported stub carries the original constant
    assert "\ntheorem kelly_core (p" not in probe
    assert "import Problems.sylvester_gallai.proofs.L_kelly_core" in probe
    # the absurd bridge: defeq arm + push_neg arm, inside the namespace
    assert "absurd @kelly_core" in probe
    assert "| exact kelly_core_disproof_claim" in probe
    assert "| (push Not; exact kelly_core_disproof_claim)" in probe
    assert "| (push_neg; exact kelly_core_disproof_claim)" in probe
    assert probe.index("absurd") < probe.index("end Problems")
    # no slug declaration -> nothing to certify
    assert _disprove.build_probe(
        "import Mathlib\ntheorem other : True := trivial\n",
        slug="kelly_core", goal_lean_path="P/x/proofs/L_kelly_core.lean") is None


def test_teaching_hands_the_negation_and_the_way_out() -> None:
    # the negation shows the TYPE alone — wrapping the full declaration
    # (`¬ (theorem s3497 : …)`) handed the agent an un-Lean target it
    # could not possibly state (three decline loops, mathd_algebra_433,
    # 2026-08-27)
    t = _disprove.teaching("theorem kelly_core : 1 = 2", "probe failed")
    assert "¬ (1 = 2)" in t
    assert "theorem kelly_core" not in t
    assert "return_to_nl" in t
    assert "disprove" in t
    # binder-style head: dropping binders would drop quantifiers —
    # describe, never misquote
    t2 = _disprove.teaching("theorem foo (p : Nat) : False", "x")
    assert "¬ (False)" not in t2
    assert "universally quantified" in t2


def test_the_claim_head_is_the_attempts_own_sid_token() -> None:
    """The pipeline seeds patch.lean as `theorem s<id>` (the locked
    signature) — never the goal slug. The goal-slug-only lookup
    certified ZERO real submissions in the gate's first two days
    (flagship: 0 disproved all-time; local: last disproved the night
    before the gate shipped). The sid head must certify, renamed to the
    same `<slug>_disproof_claim` so the bridge and fq name are
    untouched; the bare goal-slug head stays accepted as the belt."""
    sid_patch = PATCH.replace("theorem kelly_core (p : Nat)",
                              "theorem s3497 (p : Nat)")
    probe = _disprove.build_probe(
        sid_patch, slug="kelly_core", claim_slug="s3497",
        goal_lean_path="Problems/sylvester_gallai/proofs/L_kelly_core.lean")
    assert probe is not None
    assert "theorem kelly_core_disproof_claim (p : Nat)" in probe
    assert "theorem s3497" not in probe
    # the bridge still negates the GOAL's constant
    assert "absurd @kelly_core" in probe
    # neither head declared -> still nothing to certify
    assert _disprove.build_probe(
        "import Mathlib\ntheorem other : True := trivial\n",
        slug="kelly_core", claim_slug="s3497",
        goal_lean_path="P/x/proofs/L_kelly_core.lean") is None
    # the refusal names the head the agent actually owns
    from Tooling.pipeline import _axiom  # noqa: F401 — parity import
    v = _disprove.run_disproof_gate(
        workspace=Path("."), attempts_dir=Path("."),
        patch_text="import Mathlib\n", slug="kelly_core",
        goal_lean_path="P/x/proofs/L_kelly_core.lean",
        locked_signature=None, axiom_whitelist=[],
        problem="sylvester_gallai", claim_slug="s3497")
    assert not v.ok and "theorem s3497" in v.detail


def test_backward_hands_the_gate_its_sid_token() -> None:
    src = Path("Tooling/pipeline/backward.py").read_text(encoding="utf-8")
    assert "claim_slug=sid_token" in src


def test_gate_verdicts_ride_the_axiom_gate(tmp_path, monkeypatch) -> None:
    from Tooling.pipeline import _axiom

    class _R:
        def __init__(self, ok, reason=None, detail=None):
            self.ok = ok
            self.failure_reason = reason
            self.detail = detail

    monkeypatch.setattr(_axiom, "axiom_gate",
                        lambda *a, **k: _R(True))
    v = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path, patch_text=PATCH,
        slug="kelly_core",
        goal_lean_path="Problems/sylvester_gallai/proofs/L_kelly_core.lean",
        locked_signature="sig", axiom_whitelist=[],
        problem="sylvester_gallai")
    assert v.ok and "kernel-verified disproof" in v.detail
    assert (tmp_path / _disprove.PROBE_FILENAME).exists(), (
        "the certified unit must land in attempts_dir so "
        "collect_artifacts preserves it with the death row")
    monkeypatch.setattr(_axiom, "axiom_gate",
                        lambda *a, **k: _R(False, "axiom_violation", "sorryAx"))
    v = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path, patch_text=PATCH,
        slug="kelly_core",
        goal_lean_path="Problems/sylvester_gallai/proofs/L_kelly_core.lean",
        locked_signature="sig", axiom_whitelist=[],
        problem="sylvester_gallai")
    assert not v.ok and "axiom_violation" in v.detail
    assert "return_to_nl" in v.detail


def test_a_gateway_outage_is_not_the_agents_disproof_failing(
        tmp_path, monkeypatch) -> None:
    """`axiom_gate` grew its third arm on 08-12 precisely so a gateway
    outage stops being charged to the mathematics — and this caller threw
    the classification away, folding `verify_infra` into teaching prose.
    Backward then aborts `agent_declined`: attempts++, a possible shelve
    review, and the agent told its disproof did not certify, for a
    gateway that was down (owner ruling 2026-09-06)."""
    from Tooling.pipeline import _axiom

    class _R:
        def __init__(self, ok, reason=None, detail=None):
            self.ok = ok
            self.failure_reason = reason
            self.detail = detail

    monkeypatch.setattr(
        _axiom, "axiom_gate",
        lambda *a, **k: _R(False, "verify_infra", "gateway unreachable"))
    v = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path, patch_text=PATCH,
        slug="kelly_core",
        goal_lean_path="Problems/sylvester_gallai/proofs/L_kelly_core.lean",
        locked_signature="sig", axiom_whitelist=[],
        problem="sylvester_gallai")
    assert not v.ok
    assert v.infra_reason == "verify_infra"
    # …and a REAL gate failure still teaches, carrying no infra reason.
    monkeypatch.setattr(
        _axiom, "axiom_gate",
        lambda *a, **k: _R(False, "axiom_violation", "sorryAx"))
    v2 = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path, patch_text=PATCH,
        slug="kelly_core",
        goal_lean_path="Problems/sylvester_gallai/proofs/L_kelly_core.lean",
        locked_signature="sig", axiom_whitelist=[],
        problem="sylvester_gallai")
    assert not v2.ok and v2.infra_reason == ""
    # the wiring, pinned the way this file pins the sid_token hand-off
    src = Path("Tooling/pipeline/backward.py").read_text(encoding="utf-8")
    assert "verdict.infra_reason" in src


def test_backward_routes_disprove_before_the_generic_map() -> None:
    """Mechanism pin: the disprove branch runs the gate and is the only
    site in backward that emits agent_infeasible; bare unprovable gets
    the teaching abort."""
    src = Path("Tooling/pipeline/backward.py").read_text(encoding="utf-8")
    assert "run_disproof_gate" in src
    assert src.count('"agent_infeasible"') == 1
    i = src.index("DECLINE_UNPROVABLE:")
    assert "kernel-checked proof" in src[i - 200: i + 600] or \
        "kernel-checked proof" in src


# =====================================================================
# Post-mortem 2026-09-08 — the probe could not accept ANY answer on a
# goal whose statement opens with an implicit binder.
#
# union_closed g10948 / g10949 / g10952, 20:58Z -> 05:03Z: eleven
# spawns, 4-6 minutes apart, every one refused with the same
# `Type mismatch` at the same column. `absurd <slug>` elaborates the
# constant with its leading `{alpha : Type}` / `[DecidableEq alpha]`
# binders EAGERLY INSTANTIATED to metavariables, so the negation the
# bridge demanded was the negation of the instantiated body — carrying
# a live `?m.3` — while the gate's own message told the agent to state
# the closed `¬ (∀ {α} [DecidableEq α], …)`.
# The two can never unify.
# =====================================================================

#: The real error, verbatim from the g10948 probe (dead_attempt 4891),
#: shortened in the middle. The `?m.3` is the whole post-mortem: alpha
#: was never quantified in the type the probe asked for.
REAL_MISMATCH = """\
_disproof.lean:78:19: error: Type mismatch
  four_target_block_uniformity_disproof_claim
has type
  ¬∀ {α : Type} [inst : DecidableEq α] (C D : Finset (Finset α)),
      C = {I ∪ X ∪ U} → ∀ A ∈ D, X ⊆ A ∨ Disjoint X A
but is expected to have type
  ∃ C D I J X U V T,
    (C = {I ∪ X ∪ U, I ∪ X ∪ V} ∨ C = {I ∪ U, I ∪ X ∪ V}) ∧
      (∀ ⦃A B : Finset ?m.3⦄, A ∈ D → B ∈ C → A ∪ B ∈ C) ∧
        ∃ A ∈ D, ¬V ⊆ A ∧ ¬Disjoint V A
"""

IMPLICIT_PATCH = """import Mathlib

namespace Problems.p

-- decline: disprove
theorem s27363 : ¬ (∀ {α : Type} [DecidableEq α] (s : Finset α), s ⊆ s) := by
  sorry

end Problems.p
"""


def test_the_bridge_negates_the_constants_declared_type() -> None:
    """`absurd @<slug>`, never `absurd <slug>` — the one character that
    decides whether a goal with an implicit binder can be disproved at
    all. `@` suppresses implicit-argument insertion, so the constant
    keeps the type its file declares and the demanded negation is the
    closed one the teaching message promises."""
    probe = _disprove.build_probe(
        IMPLICIT_PATCH, slug="four_target_block_uniformity",
        claim_slug="s27363",
        goal_lean_path="Problems/p/proofs/L_four_target_block_uniformity.lean")
    assert probe is not None
    assert "absurd @four_target_block_uniformity" in probe
    # the regression itself: the bare form must never come back
    assert "absurd four_target_block_uniformity" not in probe
    # the reason is recorded where the next reader of the bridge is
    assert "?m" in _disprove._ABSURD_AT_WHY
    assert "instance-implicit" in _disprove._ABSURD_AT_WHY


def test_expected_type_is_lifted_out_of_the_mismatch() -> None:
    """The probe's demanded type is the one thing the agent can copy.
    Every one of the eleven refusals cut it off: `gate.detail[:400]`
    ended two lines ABOVE `but is expected to have type`, so the agent
    was told to match a type it was never shown."""
    ty = _disprove.expected_type(REAL_MISMATCH)
    assert ty.startswith("∃ C D I J X U V T,")
    assert "Disjoint V A" in ty            # the whole block, not line 1
    assert "has type" not in ty            # not the claim's own type
    assert ty.splitlines()[0] == ty.splitlines()[0].lstrip()   # dedented
    # a failure that is not a mismatch has none, and says so quietly
    assert _disprove.expected_type("error: unknown identifier 'foo'") == ""
    assert _disprove.expected_type(None) == ""


def test_the_refusal_carries_the_expected_type_verbatim() -> None:
    t = _disprove.teaching("theorem s1 : 1 = 2", "probe failed",
                           _disprove.expected_type(REAL_MISMATCH))
    assert "∃ C D I J X U V T," in t
    assert "state this verbatim" in t
    # ...and the old shape (no expected type known) still reads clean
    t0 = _disprove.teaching("theorem s1 : 1 = 2", "probe failed")
    assert "state this verbatim" not in t0
    assert "¬ (1 = 2)" in t0


def test_the_raw_error_is_clipped_head_and_tail_never_head_alone() -> None:
    """A Lean type mismatch puts the demanded type LAST, so a head-only
    slice drops exactly the half that matters — which is what a 400-char
    cut did, eleven times in eight hours."""
    long = "HEAD" + ("x" * 5000) + "TAIL"
    clipped = _disprove._clip(long)
    assert clipped.startswith("HEAD") and clipped.endswith("TAIL")
    assert len(clipped) < len(long)
    # short errors pass through whole
    assert _disprove._clip("  boom  ") == "boom"
    assert _disprove._clip(None) == ""


def test_a_gate_refusal_is_tagged_and_counted(tmp_path, monkeypatch) -> None:
    """The DB cannot tell a disprove-road refusal from any other
    `agent_declined` row, and the burn cap must count exactly those."""
    from Tooling.pipeline import _axiom

    class _R:
        ok = False
        failure_reason = "lake_build_error"
        detail = REAL_MISMATCH

    monkeypatch.setattr(_axiom, "axiom_gate", lambda *a, **k: _R())
    v = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path, patch_text=IMPLICIT_PATCH,
        slug="four_target_block_uniformity",
        goal_lean_path="Problems/p/proofs/L_four_target_block_uniformity.lean",
        locked_signature="theorem s27363 : 1 = 2", axiom_whitelist=[],
        problem="p", claim_slug="s27363")
    assert not v.ok and v.infra_reason == ""
    assert v.detail.startswith(_disprove.REFUSAL_MARKER)
    assert "∃ C D I J X U V T," in v.detail, (
        "the expected type must reach the agent — the 400-char slice "
        "cut it off on all eleven refusals")
    # a head-less patch is refused by the same road and tagged the same
    v2 = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path,
        patch_text="import Mathlib\n",
        slug="x", goal_lean_path="P/p/proofs/L_x.lean",
        locked_signature=None, axiom_whitelist=[], problem="p",
        claim_slug="s1")
    assert v2.detail.startswith(_disprove.REFUSAL_MARKER)

    # ...but an INFRA verdict is not a refusal and must never be counted
    class _I(_R):
        failure_reason = "verify_infra"

    monkeypatch.setattr(_axiom, "axiom_gate", lambda *a, **k: _I())
    v3 = _disprove.run_disproof_gate(
        workspace=tmp_path, attempts_dir=tmp_path, patch_text=IMPLICIT_PATCH,
        slug="four_target_block_uniformity",
        goal_lean_path="Problems/p/proofs/L_four_target_block_uniformity.lean",
        locked_signature=None, axiom_whitelist=[], problem="p",
        claim_slug="s27363")
    assert v3.infra_reason == "verify_infra"
    assert _disprove.REFUSAL_MARKER not in v3.detail


def _deaths_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE dead_attempts (target_id INTEGER,"
                 " target_kind TEXT, failure_reason TEXT, failure_detail TEXT)")
    return conn


def test_refusal_count_sees_only_this_goals_gate_refusals() -> None:
    conn = _deaths_db()
    tagged = _disprove._refusal("disproof not certified: ...")
    rows = [
        (10948, "Goal", "agent_declined", tagged),
        (10948, "Goal", "agent_declined", tagged),
        (10948, "Goal", "lake_build_error", "unrelated failure"),
        (10948, "Goal", "agent_declined", None),          # NULL detail
        (10949, "Goal", "agent_declined", tagged),        # another goal
        (10948, "Problem", "agent_declined", tagged),     # not a goal row
    ]
    conn.executemany("INSERT INTO dead_attempts VALUES (?,?,?,?)", rows)
    assert _disprove.refusal_count(conn, 10948) == 2
    assert _disprove.refusal_count(conn, 10949) == 1
    assert _disprove.refusal_count(conn, 99999) == 0


def test_two_refusals_park_the_goal_instead_of_a_third_spawn() -> None:
    """The burn: five spawns per goal on three goals, because a refused
    disproof was an ordinary `agent_declined` and the goal simply got
    re-dispatched until its attempts cap."""
    from Tooling.state import failures

    assert _disprove.PARK_AFTER_REFUSALS == 2
    prefix = _disprove.park_prefix(2)
    # a gate message must name an action its reader can take
    assert "Strategist review" in prefix
    assert "ConfirmShelve" in prefix and "Inject" in prefix
    # …and the Strategist's dossier digests each dead attempt to its
    # FIRST line: a park reason at the tail is one it never reads
    from Tooling.agent.context import _digest_failure
    parked = prefix + _disprove._refusal("disproof not certified: …")
    digest = _digest_failure("disproof_probe_exhausted", parked)
    assert "parked for Strategist review" in digest

    # the reason exists, stops the in-session retry loop, and routes to
    # review — the same destination as agent_shelved, by the framework's
    # count rather than the agent's ask
    assert "disproof_probe_exhausted" in failures.REGISTRY
    assert "disproof_probe_exhausted" in failures.TERMINAL_DECLINE_REASONS
    assert not failures.is_infra("disproof_probe_exhausted")
    assert "disproof_probe_exhausted" not in failures.AGENT_DECLINE_REASONS
    assert failures.draft_verdict_class("disproof_probe_exhausted") == "refused"

    src = Path("Tooling/state/transitions.py").read_text(encoding="utf-8")
    i = src.index('failure_reason == "disproof_probe_exhausted"')
    assert "_enqueue_strategist_review" in src[i:i + 400]

    # and backward reaches the cap through the counter, not a constant
    bsrc = Path("Tooling/pipeline/backward.py").read_text(encoding="utf-8")
    assert "_disproof_refusals(conn, goal_id)" in bsrc
    assert "_DISPROOF_PARK_AFTER" in bsrc
    assert '"disproof_probe_exhausted"' in bsrc


# ---------------------------------------------------------------------
# The bridge against a real toolchain — opt-in (ASTERISM_REAL_LAKE=1).
# The positive arms and the NEGATIVE one in a single elaboration: `@`
# must make a correct negation certify without making a WRONG one
# certify.
# ---------------------------------------------------------------------

_BRIDGE_PROBE = """import Mathlib

namespace AsterismDisproofBridgeTest

theorem orig {α : Type} [DecidableEq α] (s t : Finset α)
    (h : s ⊆ t) : s ∩ t = s := Finset.inter_eq_left.mpr h

-- (A) exactly the negation, binders as the agent writes them
axiom claimA : ¬ (∀ {α : Type} [DecidableEq α] (s t : Finset α),
    s ⊆ t → s ∩ t = s)
example : False :=
  absurd @orig
    (by first
      | exact claimA
      | (push Not; exact claimA)
      | (push_neg; exact claimA))

-- (B) the pushed form — the push arm must match it
axiom claimB : ∃ (α : Type) (_ : DecidableEq α) (s t : Finset α),
    s ⊆ t ∧ s ∩ t ≠ s
example : False :=
  absurd @orig
    (by first
      | exact claimB
      | (push Not; exact claimB)
      | (push_neg; exact claimB))

-- (C) the negation of a DIFFERENT statement — MUST be refused
axiom claimC : ¬ (∀ {α : Type} [DecidableEq α] (s t : Finset α),
    s ⊆ t → s ∪ t = t)
example : False :=
  absurd @orig
    (by first
      | exact claimC
      | (push Not; exact claimC)
      | (push_neg; exact claimC))

end AsterismDisproofBridgeTest
"""


@pytest.mark.real_lake
def test_the_bridge_accepts_a_correct_negation_and_refuses_a_wrong_one():
    from Tooling.quality import lake_probe
    workspace = Path(__file__).resolve().parents[1]
    run = lake_probe.run_lean_source(workspace, _BRIDGE_PROBE,
                                     prefix="_disproof_bridge")
    assert not run.infra, run.output
    # exactly ONE error, on the (C) bridge — arms A and B certified
    wrong_bridge = _BRIDGE_PROBE.splitlines().index(
        "      | (push_neg; exact claimC))") + 1
    assert run.error_lines == frozenset({wrong_bridge}), run.output
    assert "claimC" in run.output and "expected to have type" in run.output
