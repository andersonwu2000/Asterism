"""`Tooling.experiments.push_wake` — one two-turn Strategist push in a
rewound scratch workspace (the 2026-09-03 push experiment, arm B).

The runner writes: it mints a pipeline row, compiles a Context into
`.attempts/`, and spawns the seat against the workspace it is handed.
Pointed at the live workspace it would do all of that inside a running
daemon's state, so the guard is the first thing it does — before the
chdir that would make every workspace look like the current one.
"""
from __future__ import annotations

import io
import json
import sys

import pytest

from Tooling import experiments
from Tooling.experiments import push_wake


def test_push_wake_refuses_a_workspace_a_daemon_owns(tmp_path):
    """A `daemon.pid` beside the DB means the workspace is somebody
    else's; the push must refuse it rather than write into a live run."""
    ws = tmp_path / "live"
    (ws / ".asterism").mkdir(parents=True)
    (ws / "asterism.db").write_text("", encoding="utf-8")
    (ws / ".asterism" / "daemon.pid").write_text("4242 0.0", encoding="utf-8")
    with pytest.raises(SystemExit, match="scratch"):
        push_wake.assert_scratch(ws)


def test_push_wake_accepts_a_scratch_workspace(tmp_path):
    """The negative half: a workspace with no daemon marker passes, so
    the guard above is about the marker and not about refusing always."""
    ws = tmp_path / "scratch"
    (ws / ".asterism").mkdir(parents=True)
    (ws / "asterism.db").write_text("", encoding="utf-8")
    push_wake.assert_scratch(ws)


def test_a_runner_hardens_the_console_before_it_enters_the_pipeline(monkeypatch):
    """These runners are entry points into the same pipeline the CLI
    enters, and the CLI hardens the console first (`_force_utf8_io`).
    They did not: on a cp950 console the `⚠` in a length warning raised
    UnicodeEncodeError INSIDE the wake, and arm C run 2 of the push
    experiment (2026-09-03) died with its proposal written, its
    Adversary round spent and nothing committed."""
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp950"))
    experiments.harden_console()
    print("⚠ i ∉ A")          # the two characters that killed the run
    sys.stdout.flush()
    assert "⚠ i ∉ A" in sys.stdout.buffer.getvalue().decode("utf-8")


# ---------------------------------------------------------------------
# theory_wake — the 2026-09-04 theory-wake experiment (arm 3)
# ---------------------------------------------------------------------

def test_theory_verdict_parser_takes_the_three_criteria_rubric():
    """`theory_judge.md` adjudicates 1..3 (Value / Relation / Rigour),
    not the batch judge's 1..5 — and `adversary.parse_verdict` refuses
    exactly that file, so the theory wake needs its own reader. Bending
    the shared parser instead would move the batch judge's contract."""
    from Tooling.experiments import theory_wake
    from Tooling.pipeline import adversary

    text = json.dumps({"criteria": {
        "1": ["clear: the persistent-coordinate statement is on no record"],
        "2": ["clear: it implies main in three lines; the wall is the "
              "chain step, attacked in Lemma 2"],
        "3": ["clear: reran the n<=5 census, 1,171,932 families"]},
        "reservations": ["the 6-point evidence is random, not exhaustive"]})
    v, err = theory_wake.parse_theory_verdict(text)
    assert err == ""
    assert v["verdict"] == "pass"
    assert v["criticisms"] == []
    assert v["reservations"] == [
        "the 6-point evidence is random, not exhaustive"]
    # The control: the batch parser rejects the very same bytes.
    assert adversary.parse_verdict(text)[0] is None


def test_theory_verdict_parser_refuses_a_missing_criterion():
    from Tooling.experiments import theory_wake
    text = json.dumps({"criteria": {"1": ["clear: new"],
                                    "2": ["clear: implies main"]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert v is None
    assert "3" in err


def test_theory_verdict_carries_the_fired_bullets_verbatim():
    """The fired bullets are what goes back to the author, so the
    objection text must survive the parse unedited — only the criterion
    label is added."""
    from Tooling.experiments import theory_wake
    objection = ("fired: Theorem 2's proof assumes |F_x| >= |F|/2, which "
                 "is the conjecture itself — close it or label it a "
                 "conjecture")
    text = json.dumps({"criteria": {
        "1": ["clear: not in the owner's notes"],
        "2": ["clear: implies main; the wall is Lemma 3"],
        "3": [objection, "fired: the n=6 census could not be reproduced"]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert err == ""
    assert v["verdict"] == "rebut"
    assert v["criticisms"] == [
        "[criterion 3] " + objection[len("fired: "):],
        "[criterion 3] the n=6 census could not be reproduced"]


def test_theory_verdict_parser_refuses_a_bare_clear():
    from Tooling.experiments import theory_wake
    text = json.dumps({"criteria": {"1": ["clear"],
                                    "2": ["clear: implies main"],
                                    "3": ["clear: reran the census"]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert v is None
    assert "bare" in err


def test_hide_owner_notes_empties_the_context_section(tmp_path):
    """`--hide-owner-notes` is the arm-3h variable: the Context must
    carry no `## Owner's notes` at all. The section is a module-level
    function the compiler calls by attribute, so the flag replaces it —
    and the control half asserts the notes ARE there without the flag,
    or the arm would be measuring nothing."""
    from Tooling.agent import context as _ctx
    from Tooling.experiments import theory_wake
    from Tooling.state import intent as _intent
    from Tooling.state import project_docs as pd

    pd.write(tmp_path, "Combinatorics", "user/split_note.md",
             "# SPLIT: abundance across a cut\n\nbody\n")
    who = _intent.ProblemIntent(problem="Combinatorics.union_closed")
    control = _ctx._section_owner_notes(who, tmp_path)
    assert control and control[0] == "## Owner's notes"

    original = theory_wake.hide_owner_notes()
    try:
        assert _ctx._section_owner_notes(who, tmp_path) == []
        assert "## Owner's notes" not in "\n".join(
            _ctx._section_owner_notes(who, tmp_path))
    finally:
        _ctx._section_owner_notes = original
    assert _ctx._section_owner_notes(who, tmp_path) == control
