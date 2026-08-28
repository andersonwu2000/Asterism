"""Judge provenance survives the write path (calibration survey P1-P4,
2026-08-29).

The survey found the calibration transcript being destroyed daily:
`record_rejection` hard-coded verdict=NULL (89 final verdicts gone),
dialogue kept only criticisms (every rejection round's clear-reasons and
reservations dropped), and no row said which model under which rubric
judged. These pins keep the bleeding stopped.
"""
from __future__ import annotations

import json
import sqlite3

from Tooling.state import db, programme


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at) VALUES ('P', '')")
    return c


_JUDGE = {"model": "gpt-5.6-sol", "provider": "codex",
          "effort": "high", "rubric_sha": "ab12cd34ef56ab78"}


def _verdict(ruling: str = "pass") -> dict:
    return {"verdict": ruling, "criticisms": [], "reservations": ["r1"],
            "criteria": {k: ["clear: holds"] for k in "12345"},
            "_judge": dict(_JUDGE)}


def test_passed_row_carries_the_judge_stamp() -> None:
    c = _conn()
    programme.record_pass(c, "P", "body", _verdict(), [], 1, None)
    r = c.execute("SELECT judge_model, judge_provider, judge_effort,"
                  " rubric_sha FROM programme_revisions").fetchone()
    assert tuple(r) == ("gpt-5.6-sol", "codex", "high",
                        "ab12cd34ef56ab78")


def test_rejected_row_keeps_its_final_verdict_and_stamp() -> None:
    """P3: the wrongful-kill audit reads exactly this column — it was
    hard-coded NULL until 2026-08-29."""
    c = _conn()
    v = _verdict("rebut")
    programme.record_rejection(c, "P", "body", [], 3,
                               discard_reason="rounds exhausted",
                               discard_channel="x", verdict=v)
    r = c.execute("SELECT verdict, judge_model FROM programme_revisions"
                  " WHERE status='rejected'").fetchone()
    assert r["verdict"] is not None
    assert json.loads(r["verdict"])["verdict"] == "rebut"
    assert r["judge_model"] == "gpt-5.6-sol"
    # A provider-failure discard genuinely has no verdict — stays NULL,
    # never a fabricated one.
    programme.record_rejection(c, "P", "body2", [], 0,
                               discard_channel="spawn_fast_fail")
    r2 = c.execute("SELECT verdict FROM programme_revisions"
                   " WHERE body='body2'").fetchone()
    assert r2["verdict"] is None


def test_rebuttal_dialogue_rounds_carry_the_full_verdict() -> None:
    """P4 mechanism pin on the wake source (house style): criticisms
    alone dropped clear-reasons and reservations — the calibration
    transcript is the whole verdict object."""
    src = open("Tooling/pipeline/strategist/wake.py",
               encoding="utf-8").read()
    assert '"criticisms": verdict["criticisms"],' in src
    assert '"verdict": verdict,' in src
    # And the discard path recovers the last judge verdict from that
    # dialogue tail (P3's feeder).
    assert 'e.get("role") == "adversary"' in src
