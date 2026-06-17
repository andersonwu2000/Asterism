"""File-size ratchet — stop the biggest modules from silently regrowing.

Each watermark below is the file's line count at the time of the
dedup.py → cleanup/ extraction (2026-06), rounded up to the next multiple
of 50. Existing debt is grandfathered; GROWTH is blocked: a file may
shrink freely, but exceeding its watermark fails this test. If you
legitimately must exceed a limit, prefer splitting the file (as dedup.py
was split into `cleanup/`); only consciously bump the number here — in
the same PR as the growth, so the increase is visible in review.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# {relative path: max line count}
_WATERMARKS = {
    "Tooling/quality/librarian/dedup.py": 1900,
    # 2850→2900 classify size gate; →3000 Defs section-context + ownership
    # guard; →3050 same-path race lock; →3100 docstring-aware slicing;
    # →3200 cross-problem shared-def redirect + variable-block dedupe +
    # classify Library-tree context (stokes, 2026-06-11) — conscious bumps.
    # This file is OVERDUE a split (librarian work-kinds → submodules).
    # 3400→3450: _toposort_intra_file Defs-first tie-break — hoist
    # implicitly-used instances (typeclass, never named → no usage edge)
    # above their proof users (stokes PerBumpStokes instBdryOriented migrate
    # build failure) — 2026-06-16 — conscious bump.
    # 3450→3500: per-file cleanup hard Mathlib-PR gate (build must be
    # warning-free → fail unit) + redundant variable-block collapse in
    # _run_cleanup — 2026-06-17 — conscious bump.
    # 3500→3550: _reorder_decls_by_intrafile_refs — post-cleanup re-derive
    # intra-file decl order from the FINAL file's references (dedup/simplify
    # can rewrite a proof to cite a sibling, introducing a forward ref
    # file_order, frozen at classify, never reflects — eckart_young whole-
    # Library build failure) — 2026-06-17 — conscious bump.
    # 3550→3600: migrate hardening for residue_thm shapes — pull `open X in`
    # into the decl's slice (don't hoist a scoped-open above `namespace`) +
    # self_namespaces strip (decls declared under a Mathlib-extending
    # namespace like `Complex.windingNumber`) — 2026-06-17 — conscious bump.
    # 3600→3700: classify size gate accounts for the SCC file merge —
    # `_plan_usage_and_canon` (extracted from commit_classify, shared) +
    # `verify_merged_file_sizes` (reject a usage-cycle group that merges over
    # budget → re-classify, instead of a longFile STALL) — 2026-06-18.
    # 3700→3600: removed 7 dead v0.2/v0.3-vestigial functions (the
    # bridge/cleanup "re-gate the cone" cluster — _regate_touched +
    # _default_regate_build + _snapshot_problem_library + _restore_snapshot +
    # _problem_library_files, superseded by the mechanical bridge Gate B — plus
    # _importers_of + _normalize_stmt) — 2026-06-18 — tighten.
    "Tooling/pipeline/librarian.py": 3600,
    # dispatcher 2750→2800 + db 2450→2500: awaiting_human observability
    # (startup + idle-exit log of paused problems) + scope-aware idle exit
    # via db.dispatchable_open_goals — a paused P12 read as a multi-hour
    # hang across two sessions (2026-06-12) — conscious bumps.
    # dispatcher 2800→2900 + db 2500→2600: reconcile_stuck_states — per-tick
    # safety net for orphaned pending_review + NULL-outcome Inject wedges
    # (db.problems_with_pending_review / null_inject_redispatch_specs /
    # queue_has_decision) — 2026-06-13 — conscious bumps.
    # db 2600→2650: routine-only T1 clock (last_routine_at + daemon-start
    # baseline + drop batch suppression) so the routine audit fires on its own
    # running-time cadence — 2026-06-13 — conscious bump.
    # db 2650→2750: reconcile_settled_inject_outcomes — resolve NULL-outcome
    # Inject decisions whose produced goal/strategy settled (incl. the
    # soft-shelved-subgoal deadlock that wedged P13) so they stop suppressing
    # the T4 stall trigger — 2026-06-13 — conscious bump.
    # 2026-06-14: Phase 11 'stalled' strategy status (parent-stall transition +
    # migration + reconcile backstop rework) — conscious bump.
    # dispatcher 2980→3050: PID-reuse-proof singleton lock (store pid+start_time,
    # _proc_start_time / _cmdline_is_daemon / _lock_held_by_live_daemon) — a
    # crashed daemon's reused PID had blocked every restart (2026-06-15) —
    # conscious bump.
    # db 2880→3000: shelved no longer settles an inject (P13 4284 spin fix) —
    # `has_active_inflight_inject` (stall predicate) + `has_live_inflight_inject`
    # (T0 / verify-guard suppression) + parked-target redispatch guard —
    # 2026-06-15 — conscious bump.
    # db 3000→3050: #2 `goals_reachable_excluding` (DAG-aware cascade) + #4
    # `outcome_detail` column + `set_inject_decision_outcome_detail` (decline
    # `## Why` → Strategist) — 2026-06-15 — conscious bump.
    # db 3050→3100: null_inject_redispatch_specs collapses NULL Builder/Backward
    # injects to the latest per (target,kind) — restore one in-flight worker per
    # goal on restart, not N racing workers (P13 4284 909/911/920) — 2026-06-15.
    # dispatcher 3050→3080: cascade_one missing_parent_stub → terminal shelve
    # (stop the instant no-cooldown re-dispatch spin on a goal whose own stub
    # file vanished — DB↔file drift, P13 g4437) — 2026-06-16 — conscious bump.
    # dispatcher 3080→3120: _dispatch_is_duplicate caps Builder at ONE per
    # goal regardless of decision_id (two Builders prove-in-place into one
    # L_<slug>.lean → loser's stub-snapshot restore clobbers winner's proof;
    # P13 3502/4284/4288) — 2026-06-16 — conscious bump.
    # 3120→3150: librarian STALL log surfaces failure_detail by pipeline_id
    # (df77f05) + self-start gated on integrity_verified (446533a, classify-time
    # TOCTOU) — 2026-06-17 — conscious bump.
    "Tooling/core/dispatcher.py": 3150,
    # 3100→3150: classify_cited_slug — shared citation-eligibility SoT for the
    # commit gate (_cite_gate) AND validate_file's pre-commit mirror (#8 / P2)
    # — 2026-06-17 — conscious bump.
    # 3150→3200: clear_librarian_fail_counts_for_problem — a fresh classify
    # drops stale per-attempt stall caps so a reverted+re-ingested problem does
    # not inherit a STALL (residue_thm) — 2026-06-17 — conscious bump.
    "Tooling/state/db.py": 3200,
    "Tooling/quality/librarian/cleanup/__init__.py": 50,
    # 560→640: _all_warnings (Mathlib-PR zero-warning detector, broader than
    # polish's subset) + _collapse_redundant_variable_blocks (scope-safe dup
    # variable-block tidy) + _build_for_warnings (force the mathlib standard
    # linter set on, which `lake env lean` drops) — 2026-06-17 — conscious bump.
    "Tooling/quality/librarian/cleanup/_common.py": 640,
    # 300→350: audit rewritten onto the shared LSP edit-mode retry loop
    # (`run_with_session_retries`, like builder / migrate-hole-fill) — cold-seed
    # `audited.lean` + warm incremental + --resume, `_write_mcp_config` LSP, and
    # the fence/type-invariance/zero-warning gate split out as the pure
    # `_audit_gate`. (Replaces the reverted dc30d3e `_type_generalizes`
    # drop-unused-hypothesis relaxation — an unused binder is now `_`-prefixed,
    # not deleted, so the type gate stays strictly invariant.) — 2026-06-18.
    "Tooling/quality/librarian/cleanup/audit.py": 350,
    "Tooling/quality/librarian/cleanup/decide.py": 250,
    "Tooling/quality/librarian/cleanup/mechanical.py": 250,
    "Tooling/quality/librarian/cleanup/simplify.py": 200,
}


def _line_count(rel: str) -> int:
    return len((ROOT / rel).read_text(encoding="utf-8").splitlines())


def test_files_stay_under_watermark() -> None:
    over = []
    for rel, limit in _WATERMARKS.items():
        n = _line_count(rel)
        if n > limit:
            over.append(f"{rel}: {n} lines > watermark {limit}")
    assert not over, (
        "file(s) grew past their size watermark — split the file or "
        "consciously bump the limit in this test:\n" + "\n".join(over))


def test_every_cleanup_module_has_a_watermark() -> None:
    # A new cleanup/*.py must be registered here (with its own watermark),
    # so stage modules can't grow unwatched.
    cleanup_dir = ROOT / "Tooling" / "quality" / "librarian" / "cleanup"
    unlisted = sorted(
        f"Tooling/quality/librarian/cleanup/{p.name}"
        for p in cleanup_dir.glob("*.py")
        if f"Tooling/quality/librarian/cleanup/{p.name}" not in _WATERMARKS)
    assert not unlisted, f"add a watermark for: {unlisted}"
