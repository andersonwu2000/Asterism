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
# STATUS.md lives in the NESTED internal repo (docs/internal is its own git
# repository), so it legitimately cites commits from either: framework code
# hashes resolve in the main repo, backlog/docs hashes in the internal one.
_HASH_REPOS = (_REPO, _REPO / "docs" / "internal")


def _resolves_somewhere(h: str) -> bool:
    for repo in _HASH_REPOS:
        r = subprocess.run(
            ["git", "cat-file", "-e", f"{h}^{{commit}}"],
            cwd=str(repo), capture_output=True, timeout=15)
        if r.returncode == 0:
            return True
    return False


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
            if not _resolves_somewhere(h):
                missing.append(h)
        except (OSError, subprocess.TimeoutExpired):
            pytest.skip("git unavailable")
    assert not missing, (
        f"STATUS.md cites commit hash(es) that don't exist in the main or "
        f"internal repo (amended/rebased after the note was written — "
        f"update the note): {missing}")
