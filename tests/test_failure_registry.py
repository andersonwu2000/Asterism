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
        "duplicate_strategy", "no_nl_correspondence",
    }


def test_non_agent_set_pinned():
    assert failures.NON_AGENT_REASONS == {
        "spawn_fast_fail", "agent_infeasible", "parent_needs_fix",
        "agent_shelved", "goal_not_found", "lean_file_missing",
        "missing_parent_stub", "parent_stub_not_decomposable",
        "goal_no_longer_open", "unknown_kind", "no_nl_correspondence",
    }


def test_target_cooldown_set_pinned():
    assert failures.TARGET_COOLDOWN_REASONS == {
        "spawn_fast_fail", "missing_dep", "gateway_unreachable",
        "transient_timeout", "strategist_proposal_rejected",
    }


def test_death_note_set_pinned():
    assert failures.DEATH_NOTE_REASONS == {
        "spawn_fast_fail", "quota_exhausted", "missing_dep",
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
    for r in ("agent_timeout", "agent_rc_nonzero",
              "librarian_schema_invalid", "librarian_verify_failed"):
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
