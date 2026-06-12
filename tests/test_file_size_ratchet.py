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
    "Tooling/core/dispatcher.py": 2800,
    "Tooling/state/db.py": 2500,
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
