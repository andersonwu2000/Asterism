"""Failure-reason registry (state/failures.py) — drift + behavior pins
(arch-review task #5).

Three layers of protection:
  1. BEHAVIOR SNAPSHOTS — every derived set equals the literal set its
     consumer historically hardcoded. A trait edit that would silently
     change retry/cooldown/projection behavior trips here first.
  2. FORWARD DRIFT (lint) — every `failure_reason="<literal>"` the code
     emits is a registered reason (AST-walked, same machinery as the
     failure_modes.md doc gate).
  3. REVERSE DRIFT — every registered reason is actually produced or
     mapped somewhere in Tooling (no dead vocabulary).
"""
from __future__ import annotations

import re
from pathlib import Path

from Tooling.state import failures

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------
# 1. Behavior snapshots — the historical literal sets, verbatim.
# ---------------------------------------------------------------------

def test_provider_infra_set_pinned():
    assert failures.PROVIDER_INFRA_REASONS == {
        "spawn_fast_fail", "quota_exhausted", "missing_dep",
        "gateway_unreachable", "transient_timeout",
        # 08-12: the gateway answered its own 5xx (a slot that went away
        # under a live session). Provider-infra so it never burns a goal
        # attempt — one of these used to arrive as `lake_build_error`.
        "verify_infra",
        # 08-18: a transport-level death (stream disconnected / DNS) —
        # the daemon parks behind a connectivity probe instead of
        # feeding the unclassified breaker.
        "provider_network",
        # 07-30: shutdown kills must not burn goal attempts (SG#14 class).
        "daemon_shutdown",
        # 07-30: agy provider — bad model slug / refused credentials /
        # a tool denied for want of a permissions.allow rule.
        "provider_misconfigured",
        # 08-08: OS/runtime terminated the spawn (NTSTATUS rc / Bun
        # crash banner) — the machine failed, not the mathematics.
        "system_killed",
        # 08-08: an rc nobody has classified yet. Unknown ⇒ not charged
        # to the goal; repetition escalates to the operator.
        "unclassified_spawn_failure",
        # 08-25: the MACHINE could not serve the spawn's startup (MCP
        # handshake past codex's 30s under a CPU-oversubscription
        # spike) — named so it cools instead of feeding the breaker.
        "local_overload",
    }


def test_pipeline_infra_set_pinned():
    assert failures.PIPELINE_INFRA_REASONS == {
        "strategist_noop", "strategist_schema_invalid",
        "strategist_proposal_rejected",
        "forward_no_new_goal",
    }


def test_terminal_decline_set_pinned():
    assert failures.TERMINAL_DECLINE_REASONS == {
        "agent_declined", "agent_infeasible", "parent_needs_fix",
        "agent_shelved", "agent_bailed", "goal_no_longer_open",
        "same_as_disproved", "same_as_dead_unchanged",
        "duplicate_strategy", "return_to_nl",
    }


def test_non_agent_set_pinned():
    assert failures.NON_AGENT_REASONS == {
        "spawn_fast_fail", "agent_infeasible", "parent_needs_fix",
        "agent_shelved", "goal_not_found", "lean_file_missing",
        "missing_parent_stub", "parent_stub_not_decomposable",
        "goal_no_longer_open", "unknown_kind", "return_to_nl",
        # 08-19: the group-side twin of goal_no_longer_open — the wake's
        # own group was retired mid-dialogue; nothing to teach an agent.
        "group_retired",
        "problem_not_found", "system_killed",
        "unclassified_spawn_failure",
        # 08-18: a dead NIC teaches the agent nothing either.
        "provider_network",
        # 08-25: an overloaded machine teaches it nothing too.
        "local_overload",
        # A provider config error teaches the agent nothing — the fix is
        # an operator edit to the CLI's permission/model settings.
        "provider_misconfigured",
        # v38 (08-08): worker thread died by a non-infra exception; the
        # forensic row pairs cascade_one's attempts++ (goal-7486 class).
        "worker_exception",
        # 08-12: the gateway's own 5xx / 4xx on a verify. There is no
        # lesson in "your slot went away" — the row that used to carry
        # it said `lake_build_error`, i.e. "your Lean is broken".
        "verify_infra", "framework_verify_error",
    }


def test_target_cooldown_set_pinned():
    assert failures.TARGET_COOLDOWN_REASONS == {
        "spawn_fast_fail", "missing_dep", "gateway_unreachable",
        "transient_timeout", "strategist_proposal_rejected",
        "system_killed", "unclassified_spawn_failure",
        # 08-25: one beat while the machine sheds its overload.
        "local_overload",
        # 08-18: one beat before the same target re-fires while the
        # network-park probe decides.
        "provider_network",
        # #125: ghost queue rows (no loadable Manifest) must not be
        # re-dispatched in a tight T4-pumped loop.
        "problem_not_found",
        # 08-12: a lost slot is worth one beat before the same
        # (target, kind) goes back at the same gateway.
        "verify_infra",
    }


def test_death_note_set_pinned():
    assert failures.DEATH_NOTE_REASONS == {
        "spawn_fast_fail", "quota_exhausted", "missing_dep",
        "system_killed",
    }


def test_rc_map_pinned():
    assert failures.rc_to_reason(124) == "transient_timeout"
    assert failures.rc_to_reason(126) == "quota_exhausted"
    assert failures.rc_to_reason(127) == "missing_dep"
    for rc in (1, 125, 128, 999):
        assert failures.rc_to_reason(rc) == "spawn_fast_fail"


# ---------------------------------------------------------------------
# 2. Consumers actually consume the derived views (no resurrection of a
#    private literal copy — the backward.py lesson).
# ---------------------------------------------------------------------

def test_consumers_bind_to_registry_objects():
    from Tooling.pipeline import _infra, events, _retry
    assert _infra.PROVIDER_INFRA_REASONS is failures.PROVIDER_INFRA_REASONS
    assert _infra.INFRA_REASONS is failures.INFRA_REASONS
    assert events._NON_AGENT_REASONS is failures.NON_AGENT_REASONS
    assert (_retry._TERMINAL_DECLINE_REASONS
            is failures.TERMINAL_DECLINE_REASONS)


def test_decline_mapping_codomain_registered():
    from Tooling.pipeline import DECLINE_TO_FAILURE_REASON
    unknown = set(DECLINE_TO_FAILURE_REASON.values()) - set(failures.REGISTRY)
    assert not unknown, f"decline directives map to unregistered: {unknown}"


# ---------------------------------------------------------------------
# 3. Bidirectional drift.
# ---------------------------------------------------------------------

# AST artifacts of `_str_literals` on ternary/getattr expressions — not
# reasons (e.g. `getattr(r, "failure_reason", "failed")`; the doc gate
# tolerates them because failure_modes.md contains the words).
_AST_ARTIFACTS = {"reason", "failed"}


def _emitted_reasons() -> set[str]:
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from test_doc_sot_drift import _code_failure_reasons
    return _code_failure_reasons() - _AST_ARTIFACTS


def test_every_emitted_reason_is_registered():
    """Forward lint: a new `failure_reason="x"` literal must register in
    failures.REGISTRY (one entry: origin/terminal/visibility/cooldown
    traits) — the CONFIG_SPEC upgrade for the failure vocabulary."""
    missing = sorted(_emitted_reasons() - set(failures.REGISTRY))
    assert not missing, (
        f"failure_reason literals not in failures.REGISTRY: {missing} — "
        "register each with its traits (and its failure_modes.md row)")


def test_return_value_emitted_reasons_registered():
    """Blind-spot pin (2026-07-06 doc audit): `_emitted_reasons()`'s AST
    scan only sees `failure_reason="x"` keyword literals. Reasons that
    travel via a RETURN VALUE (`_spawn_failure()` → agent_timeout /
    agent_rc_nonzero) or a positional helper arg (librarian
    `_reject("librarian_schema_invalid", …)`) were invisible, and all
    four were silently missing from the REGISTRY while doc + emitters
    agreed they exist. Pin them explicitly."""
    # 08-12: both verify-error reasons travel the same way — one through
    # a local `reason = …` (the keyword scan grabbed `"transient"` out of
    # the `v.get("transient")` inside an inline conditional and demanded
    # THAT be registered), one positionally through backward's `_abort`.
    for r in ("agent_timeout", "agent_rc_nonzero",
              "librarian_schema_invalid", "librarian_verify_failed",
              "verify_infra", "framework_verify_error"):
        assert r in failures.REGISTRY, (
            f"{r} is emitted via a non-keyword path and must stay "
            f"registered")


def test_every_registered_reason_is_produced():
    """Reverse: no dead vocabulary. A registered reason must appear as a
    string literal somewhere in Tooling/ (emitted, mapped, or classified)."""
    hay = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in (ROOT / "Tooling").rglob("*.py")
        if "__pycache__" not in p.parts)
    dead = sorted(
        r for r in failures.REGISTRY
        if not re.search(rf"[\"']{re.escape(r)}[\"']", hay))
    assert not dead, (
        f"registered but never produced/referenced in Tooling/: {dead} — "
        "remove the entry or wire the producer")


# ─── an `error` from verify is the gateway's failure, not the Lean's ───
#
# 08-12: the same gateway 500 (`no slot claimed`) reached the DB under
# three different reasons — 5 rows `gateway_unreachable` (relabelled BY
# HAND the day before, so the classifier kept producing more), 4
# `forward_no_new_goal`, and one `lake_build_error` whose own detail
# began "verify infra error". That last one burned a goal attempt and
# told the agent its Lean was broken.

def test_a_transient_verify_error_is_infra_not_mathematics():
    assert failures.verify_error_reason(
        {"error": "gateway HTTP 500: no slot claimed",
         "transient": True}) == "verify_infra"


def test_a_non_transient_verify_error_is_the_framework_asking_wrong():
    """4xx / missing target / malformed response: retrying asks the same
    wrong question again, so it gets no cooldown — but it is still not
    the mathematics failing."""
    assert failures.verify_error_reason(
        {"error": "target file not found: X.lean",
         "transient": False}) == "framework_verify_error"


def test_a_lean_failure_is_left_alone():
    """The predicate must not swallow a real build failure: that shape is
    `ok: False` WITH diagnostics and no `error` key, and it belongs to
    the agent."""
    assert failures.verify_error_reason(
        {"ok": False, "diagnostics": [{"message": "unknown identifier"}]}
    ) is None
    assert failures.verify_error_reason({"ok": True}) is None


def test_verify_infra_never_burns_an_attempt_and_teaches_nothing():
    """The two traits that were wrong in production: `lake_build_error`
    is origin 'agent' (attempts++) and agent_visible."""
    assert "verify_infra" in failures.PROVIDER_INFRA_REASONS
    assert failures.REGISTRY["verify_infra"].agent_visible is False
    assert failures.REGISTRY["framework_verify_error"].agent_visible is False


def test_no_arm_hard_codes_a_reason_for_a_verify_error():
    """Every arm must ASK, because answering separately is how they came
    to disagree. Pins the call sites, not just the predicate.

    THE THIRD ARM was missed when the first two were fixed on 08-12, and
    went on charging gateway outages to the mathematics for two more
    days: dead_attempts 3086 (08-14) reads `lake_build_error` with the
    detail "verify infra error … gateway unreachable: timed out". The
    axiom gate asks the same question as the other two and now uses the
    same answer."""
    fwd = (ROOT / "Tooling" / "pipeline" / "forward.py").read_text(
        encoding="utf-8")
    bwd = (ROOT / "Tooling" / "pipeline" / "backward.py").read_text(
        encoding="utf-8")
    axiom = (ROOT / "Tooling" / "pipeline" / "_axiom.py").read_text(
        encoding="utf-8")
    assert "verify_error_reason(v)" in fwd
    assert "verify_error_reason(v)" in bwd
    assert "verify_error_reason(v)" in axiom
    # The exact regression: an error dict answered with the Lean reason.
    assert 'failure_reason="forward_no_new_goal",\n                failure_detail=f"lake elaborate failed: {v.get(\'error\'' \
        not in fwd


def test_a_filesystem_error_is_not_the_agents_lean_failing():
    """`backward`'s outer handler covers ~450 lines of placement /
    verify / insert and labelled every escape `lake_build_error` —
    origin 'agent', attempts++, agent-visible. Measured 2026-08-15: a
    spawn the framework believed it had killed was still alive and
    called `withdraw_stub`, deleting a stub between this path's glob and
    its read; the FileNotFoundError reached the agent as "your Lean
    failed to build"."""
    bwd = (ROOT / "Tooling" / "pipeline" / "backward.py").read_text(
        encoding="utf-8")
    assert '"worker_exception" if isinstance(exc, OSError)' in bwd
    assert failures.REGISTRY["worker_exception"].origin == "framework"
    assert failures.REGISTRY["worker_exception"].agent_visible is False


def test_no_verify_outcome_is_routed_through_the_catch_all():
    """THE FOURTH ARM (2026-08-17, #213). The decomposition path's
    verify loop RAISED on both `error` and `not ok`, and the outer
    handler stamps every non-OSError escape `lake_build_error` — so a
    gateway outage burned goal attempts as "your Lean failed" on the
    arm the 08-12 fix did not reach. The guard above it only greps for
    `verify_error_reason(v)` appearing SOMEWHERE in the file, which the
    leaf-bypass arm satisfied — a string-presence test guarding a
    per-arm property. This one pins the mechanism: no raise whose
    message is a verify outcome."""
    import re
    bwd = (ROOT / "Tooling" / "pipeline" / "backward.py").read_text(
        encoding="utf-8")
    assert re.search(
        r'raise RuntimeError\(\s*f?"(verify infra error|lake build failed)',
        bwd) is None, (
        "a verify outcome is raised into the generic catch-all again — "
        "route it through verify_error_reason / an explicit _abort")


def test_zero_diagnostics_is_a_worker_failure_not_a_lean_verdict():
    """`ok=false` with NO error diagnostics carries no Lean verdict —
    it is the shape of a crashed worker or an empty reply (g7894's
    "lake build failed: no error" row, 2026-08-17) — and labelling it
    `lake_build_error` charges an infra death to the mathematics. Both
    backward verify arms split on it."""
    bwd = (ROOT / "Tooling" / "pipeline" / "backward.py").read_text(
        encoding="utf-8")
    assert bwd.count("not a Lean verdict") >= 2
    assert failures.REGISTRY["framework_verify_error"].origin == "framework"


def test_rogue_axioms_message_teaches_the_way_out():
    """2026-08-18: the bare "rogue axioms: [...]" bounced four
    native_decide proofs in one day (40-54min builds each) and taught
    nothing — the fifth arrived after the Manifest note said not to.
    The message now names the source when native_decide is the cause,
    states the whitelist is fixed, and offers the two ways out. One
    home (`failures.rogue_axioms_message`): the commit gate and
    validate_file's pre-commit mirror must never grow two spellings."""
    m = failures.rogue_axioms_message(["Lean.ofReduceBool"])
    assert "rogue axioms" in m
    assert "native_decide" in m
    assert "fixed and not negotiable" in m
    assert "decline with the cut you would make" in m
    # ...and the native_decide clause is evidence-conditional: a rogue
    # axiom that is not the native pair must not be blamed on it.
    m2 = failures.rogue_axioms_message(["Classical.somethingElse"])
    assert "native_decide" not in m2
    assert "fixed and not negotiable" in m2
