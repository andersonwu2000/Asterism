"""Kernel-certified disproof gate (owner design 2026-08-25).

A bare `-- decline: unprovable` flipped the TRUE kelly_core to
`disproved` (hard terminal + dedupe #112a poison) on the agent's
say-so — the intake channel demanded a counterexample, the work-turn
channel demanded nothing (sylvester_gallai, 2026-08-24). Now the ONLY
road to disproved is a submission that PROVES the negation, certified
in the kernel by the absurd-bridge probe."""
from pathlib import Path

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
    assert "absurd kelly_core" in probe
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
    assert "absurd kelly_core" in probe
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
