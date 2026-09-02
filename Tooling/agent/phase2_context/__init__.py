"""Phase 2 — Strategist + Forward Context.md compilation.

Strategist + Forward operate at problem-level, not goal-level — so
they bypass `compile_context` (which is hard-wired to a specific goal
row) and assemble Context.md from problem-level facts only.

Strategist sees:
  - `trigger_kind`
  - Active goal list with statements + status
  - Recent strategist_decisions + their outcomes (self-feedback)
  - Proof tree, FRONTIER view (settled subtrees collapsed; #2)
  - Charter + user word + Defs.lean
  - Pending review target (for T2)

Forward sees:
  - The argument for this brick (from queue.decision_id FK)
  - Library state (cross-problem proved lemmas)
  - TREE.md inline
  - Past Forward output history
  - Mathlib hints (loogle is agent-driven via Bash tool)

─── Package facade (2026-08-28: phase2_context.py → phase2_context/, B2) ───

Move-only split into four modules along the file's own section breaks:
`dossier.py` (the pending-review dossier: failure/adjudications/
strategies/ancestors), `outcomes.py` (batch results: delegate/
delivered-group summaries, the per-step scoreboard + `BATCHES.md`,
`_prose_label`, worker declines, pending reopens), `compile.py` (the
rest of the Strategist side — trigger/gate/stall sections, roster/
replay/plan/directive/tree/charter, `compile_strategist_context`
itself), `forward.py` (the Forward side — brief/library/history/
Programme-proof/presearch/conventions, `compile_forward_context`
itself). Every name below is re-exported so `phase2_context.X`
attribute access and `from Tooling.agent.phase2_context import X` both
keep working unchanged for every caller and the test suite.

A module-level `from .x import name` COPIES the binding, so the patch
target of a shared name is the CONSUMING module, not the defining one
— there are no recorded `monkeypatch.setattr(phase2_context, ...)` (or
any alias thereof) sites anywhere in the repo (verified 2026-08-28), so
this facade carries no split patch-target risk. One direct-import path
bypasses the facade on purpose: `pipeline/round_materials.py` imports
`_section_inject_batch_outcomes` straight from this package
(`from ..agent.phase2_context import _section_inject_batch_outcomes`)
— that resolves through this same re-export, so both paths answer to
the one function in `outcomes.py`.
"""
from __future__ import annotations

from .dossier import (
    _first_sentence,
    _section_pending_review_failure,
    _section_pending_review_adjudications,
    _section_pending_review_strategies,
    _section_pending_review_ancestors,
    _slugify_ident,
)
from .outcomes import (
    _delegate_result_lines,
    _delivered_programme_companion,
    BATCHES_COMPANION,
    _step_artifact_lines,
    _prose_label,
    _write_batches_companion,
    _section_inject_batch_outcomes,
    _DECLINE_REASONS_SURFACED,
    DECLINE_INLINE_CHARS,
    _elide_middle,
    _recent_decline_lines,
    _section_pending_reopens,
)
from .compile import (
    _CATALOG_RECENT_N,
    _section_trigger,
    _axiom_certification_note,
    _section_ingest_gate,
    _section_disproof_guidance,
    _section_stall_warning,
    _ACTIVE_GOALS_TAIL_N,
    _REVIEW_DOSSIER_CAP,
    _section_active_goals,
    _REPLAY_DETAIL_BUDGET,
    _section_failure_replay,
    _plan_note_provenance,
    PLAN_NOTE_COMPANION,
    _section_plan_note,
    _section_current_directive,
    _section_tree_inline,
    _section_charter,
    _section_user_word_strategist,
    _section_paper_index_strategist,
    compile_strategist_context,
    _write_charter_file,
    _section_groups_in_flight,
    _age_hint,
    _section_your_group,
    _section_programme_strategist,
    _section_catalog_index_strategist,
    _section_adjudications_pointer,
    _section_kb_lessons_curation,
)
from .forward import (
    _section_forward_brief,
    _section_library_inventory,
    _section_forward_history,
    _section_programme_proof,
    _group_of_decision,
    _section_conventions_for_decision,
    _section_mint_presearch,
    compile_forward_context,
)
