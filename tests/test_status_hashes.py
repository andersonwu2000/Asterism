"""STATUS.md commit-hash existence lint (task #13).

STATUS.md is the operator handoff SoT; it cites commit hashes as evidence
anchors. An amend/rebase after the note is written leaves a hash that no
longer exists (the bc7fc52 incident) — silently corrupting the handoff.
Local-only by nature (docs/internal/ is not in the main repo): skips when
the file is absent (shared checkout) or git is unavailable.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_STATUS = _REPO / "docs" / "internal" / "STATUS.md"


def test_status_cited_hashes_exist():
    if not _STATUS.exists():
        pytest.skip("no docs/internal/STATUS.md (shared checkout)")
    text = _STATUS.read_text(encoding="utf-8", errors="replace")
    # backticked 7-10 char hex tokens; require ≥1 digit (real short hashes
    # essentially always have one; pure-letter words never false-positive).
    hashes = {h for h in re.findall(r"`([0-9a-f]{7,10})`", text)
              if any(c.isdigit() for c in h)}
    if not hashes:
        pytest.skip("no hashes cited")
    missing = []
    for h in sorted(hashes):
        try:
            r = subprocess.run(
                ["git", "cat-file", "-e", f"{h}^{{commit}}"],
                cwd=str(_REPO), capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pytest.skip("git unavailable")
        if r.returncode != 0:
            missing.append(h)
    assert not missing, (
        f"STATUS.md cites commit hash(es) that don't exist (amended/rebased "
        f"after the note was written — update the note): {missing}")
