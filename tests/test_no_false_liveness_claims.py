"""No surface may call a copy live.

Three renders of one fact — `goals.status` — reach an agent at
different ages: the DB itself (via `inspect`, live), `TREE.md` (written
by the dispatcher on cascades), and the Adversary's projection (a COPY
of `TREE.md` taken when the round started). That is fine. What is not
fine is a label that ranks them wrong.

Until 2026-08-15 the framework told the judge its projection's
`TREE.md` was "LIVE, rebuilt for this round" and that "the live files
are authoritative", and the judge's own file list called it "the live
goal tree". Both pointed at the STALER of two renders and called it
truth — and the judge then fired criterion 5 on a Roadmap that was
right. Warnings on the Strategist's side had already shipped on 08-10
and were correct; nothing pinned them, so nothing noticed the judge's
side saying the opposite.

These tests pin the declarations. They are prose assertions on purpose:
the defect was prose.
"""
from __future__ import annotations

import re
from pathlib import Path

from Tooling.state import tree

ROOT = Path(__file__).resolve().parents[1]


def test_the_tree_file_says_when_it_was_written():
    """A reader comparing two renders needs to know which is older.
    Without this, a disagreement looks like someone's mistake."""
    stamp = tree._stamp()
    assert re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp), stamp
