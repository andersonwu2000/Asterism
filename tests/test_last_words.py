"""The Strategist's last words after a discarded cycle (owner rulings
2026-08-30): one short turn on the same session, three sections
(`## Facts` / `## Dead routes` / `## Most valuable`), hard cap 1000
characters with one retry to cut before truncation, no route or
roadmap. Stored on the rejected rev, shown to the successor after the
judge's last rebuttal — the author's own record, never the judge's
evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.pipeline.strategist import last_words as lw
from Tooling.state import db, programme


GOOD = """## Facts
- Fin 11 prefix `step B (D ∪ {3,10})` keeps the `Q \\ S` fibre exact; `K G D` gains `{3}`.
## Dead routes
- packet-row inequalities (rounds 1–5): none relates Charge to Mass.
## Most valuable
- the missing object is a residual-indexed source count over `Q \\ S`.
"""


# ─── the note's contract ─────────────────────────────────────────────

def test_check_accepts_the_three_sections_under_the_cap():
    assert lw.check(GOOD) == (True, "")


def test_check_names_what_is_wrong():
    assert lw.check("## Facts\n- x\n")[1] == "missing_section"
    assert lw.check(GOOD + "## Roadmap\n- next: …\n")[1] == "forbidden_header"
    assert lw.check(GOOD + "AHEAD\n1. …\n")[1] == "forbidden_header"
    assert lw.check(GOOD + ("- filler\n" * 200))[1] == "too_long"


def test_truncate_keeps_the_cap():
    long = GOOD + ("- filler\n" * 200)
    cut = lw.truncate(long)
    assert len(cut) <= lw.LIMIT and cut.startswith("## Facts")


# ─── the turn: one retry to cut, then the scissors ───────────────────

def _collect(tmp_path, notes, seen):
    """`notes[i]` is what the i-th spawn writes as `_last_words.md`."""
    attempts = tmp_path / "_a"
    attempts.mkdir(exist_ok=True)

    def fake_spawn(**kw):
        seen.append(kw)
        i = len(seen) - 1
        if i < len(notes) and notes[i] is not None:
            (kw["attempts_dir"] / lw.BASENAME).write_text(notes[i], encoding="utf-8")
        return 0

    return lw.collect(spawn=fake_spawn, attempts_dir=attempts,
                      problem_dir=tmp_path, workspace=tmp_path, sid="sid-1",
                      mcp_config_path=None, timeout_sec=60, rounds=10)


def test_a_good_note_is_taken_in_one_turn(tmp_path):
    seen: list = []
    assert _collect(tmp_path, [GOOD], seen) == GOOD
    assert len(seen) == 1
    assert seen[0]["session_id"] == "sid-1", "same session — it has the whole debate"
    assert seen[0]["prompt_path"].name == "last_words.md"
    assert not seen[0]["prompt_flags"].get("too_long")


def test_an_over_long_note_gets_one_retry_then_the_scissors(tmp_path):
    long = GOOD + ("- filler\n" * 200)
    seen: list = []
    out = _collect(tmp_path, [long, GOOD], seen)
    assert out == GOOD and len(seen) == 2
    assert seen[1]["prompt_flags"].get("too_long") is True
    seen2: list = []
    out2 = _collect(tmp_path, [long, long], seen2)
    assert len(seen2) == 2 and len(out2) <= lw.LIMIT and out2.startswith("## Facts")


def test_a_note_with_a_route_is_dropped_not_repaired(tmp_path, monkeypatch):
    from Tooling.core import degraded as _degraded
    recorded: list = []
    monkeypatch.setattr(_degraded, "record", lambda ws, kind, detail="": recorded.append(kind))
    seen: list = []
    assert _collect(tmp_path, [GOOD + "## Roadmap\n- x\n"], seen) is None
    assert recorded == ["last_words"]


def test_no_file_means_no_note(tmp_path):
    seen: list = []
    assert _collect(tmp_path, [None], seen) is None


# ─── storage and the successor's view ────────────────────────────────

def _fresh(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done) VALUES ('p', ?, 1)",
              (db.now(),))
    c.commit()
    return c


def test_last_words_ride_the_rejected_rev(tmp_path):
    c = _fresh(tmp_path)
    rid = programme.record_rejection(
        c, "p", "# Dead\n\n## Argument\n\nSECRET-DRAFT\n",
        [{"round": 1, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 1] it dies"]}],
        1, discard_reason="adversary rebuttal",
        discard_channel="strategist_proposal_rejected", last_words=GOOD)
    c.commit()
    assert isinstance(rid, int)
    row = c.execute("SELECT last_words FROM programme_revisions WHERE id = ?", (rid,)).fetchone()
    assert row["last_words"] == GOOD


def test_successor_sees_the_last_words_after_the_judges_rebuttal(tmp_path, monkeypatch):
    from Tooling.agent.phase2_context import compile as C
    from Tooling.state import intent as intent_mod
    c = _fresh(tmp_path)
    programme.record_rejection(
        c, "p", "# Dead\n\n## Argument\n\nSECRET-DRAFT\n",
        [{"round": 1, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 1] the fatal objection"]}],
        1, discard_reason="adversary rebuttal",
        discard_channel="strategist_proposal_rejected", last_words=GOOD)
    c.commit()
    attempts = tmp_path / "_a"
    attempts.mkdir()
    lines = C._section_programme_strategist(c, "p", None, attempts_dir=attempts)
    text = "\n".join(lines)
    i_reb = text.index("the fatal objection")
    i_lw = text.index("residual-indexed source count")
    assert i_reb < i_lw, "the judge's rebuttal first, the author's record after"
    assert "unverified" in text[i_reb:i_lw + 1].lower() or "own record" in text.lower()
    assert "SECRET-DRAFT" not in text
