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
    "Tooling/pipeline/librarian.py": 3400,
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
    "Tooling/core/dispatcher.py": 3050,
    "Tooling/state/db.py": 3000,
    "Tooling/quality/librarian/cleanup/__init__.py": 50,
    "Tooling/quality/librarian/cleanup/_common.py": 560,
    "Tooling/quality/librarian/cleanup/audit.py": 200,
    "Tooling/quality/librarian/cleanup/decide.py": 250,
    "Tooling/quality/librarian/cleanup/mechanical.py": 250,
    "Tooling/quality/librarian/cleanup/polish.py": 150,
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
