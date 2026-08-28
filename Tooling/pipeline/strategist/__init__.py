"""Phase 2 — Strategist pipeline (Step 6 scaffolding).

Strategist emits a single meta-level decision per invocation:
  Inject / ConfirmShelve / Reopen / EmitDirective
  / RequestUserAmend / Noop

This module covers decision validation + commit; the agent stage
(actually spawning the LLM, writing `decision.json` to attempts_dir)
is the next-session piece. The framework-side logic — schema check,
Reopen ancestor safety walk, atomic side effects, strategist_decisions
audit row, last_strategist_at touch — is implemented in full.

Stage order (docs/archive/design/phase2/pipelines.md §2.4):
  1. trigger_context  (pure)   compile input per trigger_kind
  2. failure_replay   (pure)   last 5 strategist_decisions
  3. agent            (agent)  spawn LLM, get decision.json  ← TODO
  4. self_verify      (pure)   schema + Reopen ancestor walk
  5. commit           (pure)   execute decision + audit row

Public surface:
  - DECISION_KINDS              — frozenset of valid `decision_kind`
  - parse_decision(json_text)    -> Decision | (None, error_msg)
  - verify_decision(decision, conn, problem) -> ok | error_msg
  - commit_decision(decision, conn, *, problem, tick, trigger_kind,
                    workspace, attempts_dir) -> Outcome
  - run_strategist(...)         — outer entry (stub awaiting agent stage)
"""
from __future__ import annotations

# ─── Package facade (2026-08-28: strategist.py → strategist/, B1) ───────
#
# Move-only split into four modules by pipeline stage: `model.py` (the
# Decision dataclass, decision-kind vocabulary, decision.json parser),
# `verify.py` (self_verify stage), `commit.py` (commit stage),
# `wake.py` (the outer run_strategist entry + the proposal-package gate
# + the Adversary revision loop). Every name below is re-exported so
# `strategist.X` attribute access and `from Tooling.pipeline.strategist
# import X` both keep working unchanged for the one caller
# (`dispatcher.py`'s `strategist.run_strategist`) and the test suite.
#
# A module-level `from .x import name` COPIES the binding, so the patch
# target of a shared name is the CONSUMING module, not the defining one
# — there are no recorded `monkeypatch.setattr(strategist, ...)` sites
# on this module (verified 2026-08-28), so this facade carries no split
# patch-target risk the way the gateway split did.
from .model import (
    DECISION_KINDS,
    RETURN_FLAVOURS,
    TRIGGER_KINDS,
    BATCH_DONE_LIKE,
    _PACKAGE_EXEMPT_KINDS,
    Decision,
    parse_decisions,
    parse_decision,
    _parse_one,
    _as_bool,
)
from .verify import (
    USER_AMEND_FILES,
    _authoring_group,
    _group_retired_status,
    verify_decision,
    verify_decisions,
)
from .commit import (
    CommitOutcome,
    _commit_inject_batch,
    _commit_inject_forward,
    _commit_inject_redispatch,
    _commit_delegate,
    _commit_return_to_parent,
    _commit_close_group,
    commit_decisions,
    commit_decision,
    _commit_ingest,
    _commit_one,
)
from .wake import (
    PROPOSAL_BASENAME,
    package_gate_applies,
    verify_proposal_package,
    _format_rebuttal,
    run_strategist,
    _KB_CURATION_MAX_OPS,
    _apply_kb_curation,
    _discard_proposal,
    _persist_plan,
    _rc_to_reason,
    _adversary_rc_reason,
)
