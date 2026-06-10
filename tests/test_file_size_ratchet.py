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
    "Tooling/pipeline/librarian.py": 2850,
    "Tooling/core/dispatcher.py": 2750,
    "Tooling/state/db.py": 2450,
    "Tooling/quality/librarian/cleanup/__init__.py": 50,
    "Tooling/quality/librarian/cleanup/_common.py": 500,
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
